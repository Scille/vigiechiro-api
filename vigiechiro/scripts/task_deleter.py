from flask import current_app

from .celery import celery_app


@celery_app.task
def clean_deleted_participation(participation_id):
    from ..vigiechiro.donnees import donnees
    from ..vigiechiro.fichiers import delete_fichier_and_s3
    donnees.remove({'participation': participation_id})
    for f in fichiers.find({'participation': participation_id}):
        delete_fichier_and_s3(f)


@celery_app.task
def clean_deleted_site(site_id):
    from ..vigiechiro.participations import participations
    ps = participations.find({'site': site_id})
    for p in ps:
        clean_deleted_participation(p)
    participations.remove({'site': site_id})
