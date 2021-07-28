from bson import ObjectId
from .queuer import task


@task
def clean_deleted_participation(participation_id):
    participation_id = ObjectId(participation_id)
    print('Clean donnees&fichiers linked with participation %s' % participation_id)
    from ..resources.donnees import donnees
    from ..resources.fichiers import fichiers, delete_fichier_and_s3
    res = donnees.remove({'participation': participation_id})
    if res.deleted_count != 1:
        raise RuntimeError('Error removing donnes for participation: %s' % participation_id)
    print('Removed %s donnees' % res.deleted_count)
    fs, total = fichiers.find({'participation': participation_id})
    for f in fs:
        delete_fichier_and_s3(f)
    print('Removed %s fichiers' % total)


@task
def clean_deleted_site(site_id):
    site_id = ObjectId(site_id)
    from ..resources.participations import participations
    print('Start cleaning participations linked with site %s' % site_id)
    ps, _ = participations.find({'site': site_id})
    for p in ps:
        clean_deleted_participation(p['_id'])
    res = participations.remove({'site': site_id})
    if res.deleted_count != 1:
        raise RuntimeError('Error removing participations for site: %s' % site_id)
    print('Removed %s participations' % res.deleted_count)
