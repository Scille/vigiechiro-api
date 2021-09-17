import os
from zipfile import ZipFile, ZIP_DEFLATED
from bson import ObjectId
from io import BytesIO, StringIO
import csv
from flask import current_app
from smtplib import SMTPSenderRefused

from .queuer import task
from ..resources.taxons import taxons
from ..settings import TASK_PARTICIPATION_DATASTORE_CACHE


HEADERS = ['nom du fichier',
           'temps_debut', 'temps_fin', 'frequence_mediane', 'tadarida_taxon',
           'tadarida_probabilite', 'tadarida_taxon_autre', 'observateur_taxon',
           'observateur_probabilite', 'validateur_taxon', 'validateur_probabilite']

MAX_UNCOMPRESSED_ATTACHEMENT_SIZE = 1024 * 1024  # 1mo


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
            print('cache miss !', id)
            taxons_cache[id] = taxons.find_one(id)
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


@task
def email_observations_csv(participation_id, recipient, subject, body):
    csv_data = generate_observations_csv(participation_id)
    csv_name = "participation-%s-observations.csv" % participation_id

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

    # Save the CSV in datastore
    if TASK_PARTICIPATION_DATASTORE_CACHE:
        participation_datastore = '%s/%s' % (TASK_PARTICIPATION_DATASTORE_CACHE, participation_id)
        if not os.path.exists(participation_datastore):
            os.mkdir(participation_datastore)
        csv_datastore_path = '%s/%s' % (participation_datastore, attachement[0])
        with open(csv_datastore_path, "wb") as fd:
            fd.write(attachement[2])
    else:
        csv_datastore_path = None

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
        body += "\n\nPS: Le CSV n'a pas pu être inclus car trop gros ({size:.2f}Mo zippé)\n".format(size=attachement_size_mo)
        if csv_datastore_path:
            body += "Vous pouvez contacter le support en indiquant le chemin du fichier sur le serveur: {path}\n".format(path=csv_datastore_path)

        current_app.mail.send(
            recipient=recipient,
            subject=subject,
            body=body
        )
