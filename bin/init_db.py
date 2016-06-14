#! /usr/bin/env python3

"""
Reset&configure the bdd for vigiechiro
"""

import pymongo
from datetime import datetime, timedelta

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


db = pymongo.MongoClient(host=settings.MONGO_HOST).get_default_database()


def clean_db():
    db.connection.drop_database(db.name)


def create_indexes():
    db.grille_stoc.ensure_index([('centre', pymongo.GEOSPHERE)])
    db.utilisateurs.ensure_index([
        ('email', pymongo.TEXT),
        ('pseudo', pymongo.TEXT),
        ('nom', pymongo.TEXT),
        ('prenom', pymongo.TEXT),
        ('organisation', pymongo.TEXT),
        ('tag', pymongo.TEXT)
    ], default_language='french', name='utilisateursTextIndex')
    db.taxons.ensure_index([
        ('libelle_long', pymongo.TEXT),
        ('libelle_court', pymongo.TEXT),
        ('tags', pymongo.TEXT)
    ], default_language='french', name='taxonsTextIndex')
    db.taxons.ensure_index([('libelle_long', 1)])
    db.protocoles.ensure_index([
        ('titre', pymongo.TEXT),
        ('tags', pymongo.TEXT)
    ], default_language='french', name='protocolesTextIndex')
    db.sites.ensure_index([
        ('titre', pymongo.TEXT)
    ], default_language='french', name='sitesTextIndex')
    db.sites.ensure_index([('titre', 1)])
    db.actualites.ensure_index([('_updated', -1)])
    db.fichiers.ensure_index([('titre', 1), ('mime', 1)])
    db.fichiers.ensure_index([('s3_id', 1)])
    db.fichiers.ensure_index([("lien_participation", 1) , ("mime", 1)])
    db.donnees.ensure_index([("observations.tadarida_taxon", 1) , ("observations.tadarida_probabilite", 1), ("_created", 1)])
    db.donnees.ensure_index([("observations.tadarida_taxon", 1) , ("participation" , 1)])
    db.donnees.ensure_index([("participation", 1)])


def insert_default_documents():
    # Increments document
    db.configuration.insert({
        'name': 'increments',
        'protocole_routier_count': 600
    })
    # Script worker utilisateur
    db.utilisateurs.insert({
            'pseudo': 'script_worker',
            'email': 'script_worker@email.com',
            'role': 'Administrateur',
            'tokens': {settings.SCRIPT_WORKER_TOKEN:
            datetime.utcnow() + timedelta(days=settings.SCRIPT_WORKER_EXPIRES)}
        })


def main():
    print('You are about to fully ERASE the database {green}{name}{endc}'.format(
        green='\033[92m', name=settings.MONGO_HOST, endc='\033[0m'))
    print('To continue, type YES')
    if input() != 'YES':
        raise SystemExit('You changed your mind, exiting...')
    print('Cleaning database...', flush=True, end='')
    clean_db()
    print(' Done !')
    print('Creating indexes...', flush=True, end='')
    create_indexes()
    print(' Done !')
    insert_default_documents()


if __name__ == '__main__':
    main()
