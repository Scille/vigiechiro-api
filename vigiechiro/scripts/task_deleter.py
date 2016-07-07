from bson import ObjectId
from .queuer import task


@task
def clean_deleted_participation(participation_id):
    participation_id = ObjectId(participation_id)
    print('Clean donnees&fichiers linked with participation %s' % participation_id)
    from ..resources.donnees import donnees
    from ..resources.fichiers import fichiers, delete_fichier_and_s3
    ret = donnees.remove({'participation': participation_id})
    if ret.get('ok') != 1:
        raise RuntimeError('Error removing donnes: %s' % ret)
    print('Removed %s donnees' % ret['n'])
    fs, _ = fichiers.find({'participation': participation_id})
    for f in fs:
        delete_fichier_and_s3(f)
    print('Removed %s fichiers' % len(fs))


@task
def clean_deleted_site(site_id):
    site_id = ObjectId(site_id)
    from ..resources.participations import participations
    print('Start cleaning participations linked with site %s' % site_id)
    ps, _ = participations.find({'site': site_id})
    for p in ps:
        clean_deleted_participation(p['_id'])
    ret = participations.remove({'site': site_id})
    if ret.get('ok') != 1:
        raise RuntimeError('Error removing participations: %s' % ret)
    print('Removed %s participations' % ret['n'])
