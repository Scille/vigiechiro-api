from zipfile import ZipFile, ZIP_DEFLATED
from bson import ObjectId
from io import BytesIO, StringIO
import csv
from flask import current_app
from smtplib import SMTPSenderRefused


from .queuer import task
from ..resources.fichiers import ALLOWED_MIMES_PROCESSING_EXTRA, delete_fichier_and_s3, fichiers, get_file_from_s3
from ..resources.taxons import taxons

HEADERS = ['nom du fichier',
           'temps_debut', 'temps_fin', 'frequence_mediane', 'tadarida_taxon',
           'tadarida_probabilite', 'tadarida_taxon_autre', 'observateur_taxon',
           'observateur_probabilite', 'validateur_taxon', 'validateur_probabilite']

MAX_UNCOMPRESSED_ATTACHEMENT_SIZE = 1024 * 1024  # 1mo


def generate_csv_name(participation_id):
    return "participation-%s-observations.csv" % participation_id


def retrieve_observations_csv(participation_id, csv_name):
    csv_obj = fichiers.find_one({
        'lien_participation': participation_id,
        'titre': csv_name,
        'mime': {'$in': ALLOWED_MIMES_PROCESSING_EXTRA},
        'disponible': True,
    }, auto_abort=False)
    if not csv_obj:
        return None
    return get_file_from_s3(csv_obj)


def upload_observations_csv(participation_id, csv_name, csv_data):
    from .task_participation import _create_fichier
    from ..resources.participations import participations

    p = participations.find_one(participation_id, auto_abort=False)
    if not p:
        raise RuntimeError(f"Unknown participation `{participation_id}`")
    proprietaire_id = p["observateur"]

    _create_fichier(
        titre=csv_name,
        mime=ALLOWED_MIMES_PROCESSING_EXTRA[0],
        proprietaire=proprietaire_id,
        data_raw=csv_data,
        lien_participation=participation_id,
        force_upload=True
    )


def generate_observations_csv(participation_id):
    from ..resources.donnees import donnees
    participation_id = ObjectId(participation_id)
    buff = StringIO()
    w = csv.writer(buff, delimiter=';', quotechar='"', quoting=csv.QUOTE_NONNUMERIC)
    # Add headers
    w.writerow(HEADERS)

    taxons_cache = {}
    def fetch_taxon_libelle_court(id):
        nonlocal taxons_cache
        if id not in taxons_cache:
            print('Taxon cache miss !', id)
            taxon = taxons.find_one(id, auto_abort=False)
            if not taxon:
                raise RuntimeError(f"Unknown taxon `{id}`")
            taxons_cache[id] = taxon
        return taxons_cache[id]["libelle_court"]

    def format_row(obs, titre):
        row = []
        for h in HEADERS:
            value = ''
            if h == 'nom du fichier':
                value = titre
            elif h == 'temps_debut':
                value = (obs.get(h) if obs.get(h) else '0.0')
            elif h == 'temps_fin':
                value = (obs.get(h) if obs.get(h) else '0.0')
            elif h == 'tadarida_taxon':
                value = fetch_taxon_libelle_court(obs[h])
            elif h == 'tadarida_taxon_autre':
                values = []
                for a in obs.get(h, []):
                    if a['probabilite'] >= (obs.get('tadarida_probabilite', 0) / 2):
                        values.append(fetch_taxon_libelle_court(a["taxon"]))
                value = ', '.join(values)
            elif h in ('observateur_taxon', 'validateur_taxon'):
                taxon_id = obs.get(h, None)
                if taxon_id is not None:
                    value = fetch_taxon_libelle_court(taxon_id)
            else:
                value = obs.get(h)
            row.append(value if value else '')
        return row

    entries, count = donnees.find({
        'participation': participation_id},
        sort=[('titre', 1)],
        projection={'participation': False, 'proprietaire': False, "observations.messages": False},
        additional_context={"expend": False}
    )
    print(f'Crunching {count} items')

    done = 0
    taxons_cache = {}
    for do in entries:
        done += 1
        if done % 100 == 0:
            print(f"{done}/{count}")
        for obs in do.get('observations', []):
            w.writerow(format_row(obs, do.get('titre', '')))
    return buff.getvalue().encode('utf-8')


def ensure_observations_csv_is_available(participation_id):
    participation_id = ObjectId(participation_id)
    csv_name = generate_csv_name(participation_id)

    # TEMPORARY FIX: currently csv are sometime generated without data, so
    # forcing regeranation by using the sending by email function is convenient

    # Retrieve and remove the previous observation file if any
    old_csv = current_app.data.db.fichiers.find_one({
        'lien_participation': participation_id,
        'titre': csv_name,
    })
    if old_csv:
        delete_fichier_and_s3(old_csv)
    # Regenerate CSV
    csv_data = generate_observations_csv(participation_id)
    upload_observations_csv(participation_id, csv_name, csv_data)

    # # Try to find the csv if it is already computed
    # csv_name = generate_csv_name(participation_id)
    # csv_data = retrieve_observations_csv(participation_id, csv_name)
    # if not csv_data:
    #     # CSV not available, compute it
    #     csv_data = generate_observations_csv(participation_id)
    #     upload_observations_csv(participation_id, csv_name, csv_data)
    return csv_name, csv_data


@task
def participation_generate_observations_csv(participation_id):
    participation_id = ObjectId(participation_id)
    csv_name = generate_csv_name(participation_id)

    # Retrieve and remove the previous observation file if any
    old_csv = current_app.data.db.fichiers.find_one({
        'lien_participation': participation_id,
        'titre': csv_name,
    })
    if old_csv:
        delete_fichier_and_s3(old_csv)

    # Regenerate CSV
    csv_data = generate_observations_csv(participation_id)
    upload_observations_csv(participation_id, csv_name, csv_data)


@task
def email_observations_csv(participation_id, recipient, subject, body):
    csv_name, csv_data = ensure_observations_csv_is_available(participation_id)

    if len(csv_data) < MAX_UNCOMPRESSED_ATTACHEMENT_SIZE:
        attachement = (
                csv_name,
                "text/csv",
                bytearray(csv_data)
            )
    else:
        # CSV is too big, zip it before attach
        zip_data = BytesIO()
        with ZipFile(zip_data, mode="w", compression=ZIP_DEFLATED) as zf:
            zf.writestr(csv_name, data=csv_data)

        attachement = (
                "%s.zip" % csv_name,
                "application/zip",
                bytearray(zip_data.getvalue())
            )

    try:
        current_app.mail.send(
            recipient=recipient,
            subject=subject,
            body=body,
            attachements=[attachement]
        )
    except SMTPSenderRefused:
        # Consider the size limit is the issue, so send without attachement

        attachement_size_mo = float(len(attachement[2])) / (1024 ** 2)
        body += "\n\nPS: Le CSV n'a pas pu être inclus car trop gros ({size:.2f}Mo zippé).\n".format(size=attachement_size_mo)
        body += "Vous pouvez y accéder depuis le bouton « Afficher les autres fichiers de traitement » de la page de la participation.\n"

        current_app.mail.send(
            recipient=recipient,
            subject=subject,
            body=body
        )
