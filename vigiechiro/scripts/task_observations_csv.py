from bson import ObjectId
from io import StringIO
import csv
from flask.ext.mail import Message

from .celery import celery_app


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

    def format_row(obs, titre):
        row = []
        for h in HEADERS:
            if h == 'nom du fichier':
                value = titre
            elif h == 'tadarida_taxon':
                value = obs.get(h, {})['libelle_court']
            elif h == 'tadarida_taxon_autre':
                value = ', '.join(['%s' % (a['taxon']['libelle_court'])
                    for a in obs.get(h, []) if a['probabilite'] >= (obs.get('tadarida_probabilite', 0) / 2)])
            elif h == 'observateur_taxon':
                value = ''
                if 'libelle_court' in obs.get(h, {}).keys():
                    value = obs.get(h, {})['libelle_court']
            elif h == 'validateur_taxon':
                value = ''
                if 'libelle_court' in obs.get(h, {}).keys():
                    value = obs.get(h, {})['libelle_court']
            else:
                value = obs.get(h)
            row.append(value if value else '')
        return row

    for do in donnees.find({'participation': participation_id}, sort=[('titre', 1)])[0]:
        for obs in do.get('observations', []):
            w.writerow(format_row(obs, do.get('titre', '')))
    return bytearray(buff.getvalue().encode('UTF-16LE'))


@celery_app.keep_alive_task
def email_observations_csv(participation_id, recipients, body=None):
    from ..app import app as flask_app
    with flask_app.app_context():
        if not isinstance(recipients, (list, tuple)):
            recipients = [recipients, ]
        msg = Message(subject="Observations de la participation %s" % participation_id,
                      recipients=recipients, body=body)
        msg.attach("participation-%s-observations.csv" % participation_id,
                   "text/csv", generate_observations_csv(participation_id))
        flask_app.mail.send(msg)
