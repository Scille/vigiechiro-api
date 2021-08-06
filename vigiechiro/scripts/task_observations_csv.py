from bson import ObjectId
from io import StringIO
import csv
from flask import current_app

from .queuer import task
from ..resources.taxons import taxons


HEADERS = ['nom du fichier',
           'temps_debut', 'temps_fin', 'frequence_mediane', 'tadarida_taxon',
           'tadarida_probabilite', 'tadarida_taxon_autre', 'observateur_taxon',
           'observateur_probabilite', 'validateur_taxon', 'validateur_probabilite']


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
    return bytearray(buff.getvalue().encode('utf-8'))


@task
def email_observations_csv(participation_id, recipient, subject, body):
    csv_data = generate_observations_csv(participation_id)
    current_app.mail.send(
        recipient=recipient,
        subject=subject,
        body=body,
        attachements=[
            (
                "participation-%s-observations.csv" % participation_id,
                "text/csv",
                csv_data
            )
        ]
    )
