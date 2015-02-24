#! /usr/bin/env python3

"""
Reset&configure the bdd for vigiechiro
"""

import pymongo

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
	'utilisateurs'
]

db = pymongo.MongoClient(host=settings.get_mongo_uri())[settings.MONGO_DBNAME]


def clean_db():
	for collection in COLLECTIONS:
		db[collection].drop()


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
	db.protocoles.ensure_index([
		('titre', pymongo.TEXT),
		('tags', pymongo.TEXT)
	], default_language='french', name='protocolesTextIndex')
	db.sites.ensure_index([
		('titre', pymongo.TEXT),
	], default_language='french', name='sitesTextIndex')


def main():
	db_name = '{}:{}/{}'.format(settings.MONGO_HOST, settings.MONGO_PORT, settings.MONGO_DBNAME)
	print('You are about to fully ERASE the database {green}{name}{endc}'.format(
		green='\033[92m', name=db_name, endc='\033[0m'))
	print('To continue, type YES')
	if input() != 'YES':
		raise SystemExit('You changed your mind, exiting...')
	print('Cleaning database...', flush=True, end='')
	clean_db()
	print(' Done !')
	print('Creating indexes...', flush=True, end='')
	create_indexes()
	print(' Done !')


if __name__ == '__main__':
	main()
