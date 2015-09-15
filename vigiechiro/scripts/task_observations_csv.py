from bson import ObjectId
from io import StringIO
import csv
from flask.ext.mail import Message

from .celery import celery_app


HEADERS = ['titre',
           'temps_debut', 'temps_fin', 'frequence_mediane', 'tadarida_taxon',
           'tadarida_probabilite', 'tadarida_taxon_autre', 'observateur_taxon',
           'observateur_probabilite', 'validateur_taxon', 'validateur_probabilite']


def generate_observations_csv(participation_id):
    from ..resources.donnees import donnees
    participation_id = ObjectId(participation_id)
    buff = StringIO()
    w = csv.writer(buff)
    # Add headers
    w.writerow(HEADERS)

    def format_row(obs, titre):
        row = []
        for h in HEADERS:
            if h == 'titre':
                value = titre
            elif h == 'tadarida_taxon':
                value = obs.get(h, {})['libelle_long']
            elif h == 'tadarida_taxon_autre':
                value = '\n'.join(['%s:%s' % (a['taxon']['libelle_long'], a['probabilite'])
                                   for a in obs.get(h, [])])
            else:
                value = obs.get(h)
            row.append(value if value else '')
        return row

    for do in donnees.find({'participation': participation_id})[0]:
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
