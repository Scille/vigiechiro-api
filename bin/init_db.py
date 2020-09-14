#! /usr/bin/env python3

"""
Reset&configure the bdd for vigiechiro
"""

import pymongo
from datetime import datetime, timedelta
from sys import argv

from vigiechiro import settings


COLLECTIONS = [
    'actualites',
    'donnees',
    'fichiers',
    'grille_stoc',
    'participations',
    'protocoles',
    'sites',
    'taxons',
    'utilisateurs',
    'configuration'
]


conn = pymongo.MongoClient(host=settings.MONGO_HOST)
db = conn.get_default_database()


def clean_db():
    conn.drop_database(db.name)


def ensure_indexes():
    db.grille_stoc.create_index([('centre', pymongo.GEOSPHERE)])
    db.utilisateurs.create_index([
        ('email', pymongo.TEXT),
        ('pseudo', pymongo.TEXT),
        ('nom', pymongo.TEXT),
        ('prenom', pymongo.TEXT),
        ('organisation', pymongo.TEXT),
        ('tag', pymongo.TEXT)
    ], default_language='french', name='utilisateursTextIndex')
    db.taxons.create_index([
        ('libelle_long', pymongo.TEXT),
        ('libelle_court', pymongo.TEXT),
        ('tags', pymongo.TEXT)
    ], default_language='french', name='taxonsTextIndex')
    db.taxons.create_index([('libelle_long', 1)])
    db.protocoles.create_index([
        ('titre', pymongo.TEXT),
        ('tags', pymongo.TEXT)
    ], default_language='french', name='protocolesTextIndex')
    db.sites.create_index([
        ('titre', pymongo.TEXT)
    ], default_language='french', name='sitesTextIndex')
    db.sites.create_index([('titre', 1)])
    db.sites.create_index([('protocole', 1)])
    db.actualites.create_index([('_updated', -1)])
    db.fichiers.create_index([('titre', 1), ('mime', 1)])
    db.fichiers.create_index([('s3_id', 1)])
    db.fichiers.create_index([("lien_participation", 1) , ("mime", 1)])
    db.donnees.create_index([('proprietaire', 1), ('publique', 1)])
    db.donnees.create_index([('participation', 1), ('titre', 1)])
    db.donnees.create_index([("observations.tadarida_taxon", 1) , ("observations.tadarida_probabilite", 1), ("_created", 1)])
    db.donnees.create_index([("observations.tadarida_taxon", 1) , ("participation" , 1)])
    db.queuer.create_index([('status', 1)])
    db.queuer.create_index([('submitted', 1)])


def insert_default_documents():
    # Increments document
    db.configuration.insert_one({
        'name': 'increments',
        'protocole_routier_count': 600
    })
    # Script worker utilisateur
    db.utilisateurs.insert_one({
            'pseudo': 'script_worker',
            'email': 'script_worker@email.com',
            'role': 'Administrateur',
            'tokens': {settings.SCRIPT_WORKER_TOKEN:
            datetime.utcnow() + timedelta(days=settings.SCRIPT_WORKER_EXPIRES)}
        })


def reset_db():
    print('You are about to fully ERASE the database {green}{name}{endc}'.format(
        green='\033[92m', name=settings.MONGO_HOST, endc='\033[0m'))
    print('To continue, type YES')
    if input() != 'YES':
        raise SystemExit('You changed your mind, exiting...')
    print('Cleaning database...', flush=True, end='')
    clean_db()
    print(' Done !')
    print('Creating indexes...', flush=True, end='')
    ensure_indexes()
    print(' Done !')
    insert_default_documents()


if __name__ == '__main__':
    if len(argv) == 2:
        if argv[1] == 'reset':
            reset_db()
        elif argv[1] == 'ensure_indexes':
            ensure_indexes()
        else:
            print('%s [reset|ensure_indexes]' % argv[0])
    else:
        print('%s [reset|ensure_indexes]' % argv[0])
