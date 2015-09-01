from bson import ObjectId
from .celery import celery_app


@celery_app.keep_alive_task
def clean_deleted_participation(participation_id):
    participation_id = ObjectId(participation_id)
    from ..app import app as flask_app
    with flask_app.app_context():
        from ..resources.donnees import donnees
        from ..resources.fichiers import fichiers, delete_fichier_and_s3
        donnees.remove({'participation': participation_id})
        fs, _ = fichiers.find({'participation': participation_id})
        for f in fs:
            delete_fichier_and_s3(f)


@celery_app.keep_alive_task
def clean_deleted_site(site_id):
    site_id = ObjectId(site_id)
    from ..app import app as flask_app
    with flask_app.app_context():
        from ..resources.participations import participations
        ps, _ = participations.find({'site': site_id})
        for p in ps:
            clean_deleted_participation(p['_id'])
        participations.remove({'site': site_id})
