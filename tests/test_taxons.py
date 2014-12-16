import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur


@pytest.fixture
def taxons_base(request):
    # Insert parent
    parent_id = db.taxons.insert({
        'libelle_long': 'Chiroptera',
        'libelle_court': 'Chiro',
        'description': """D'après wikipedia :
L'ordre des chiroptères regroupe des mammifères volants,
communément appelés chauvesouris, ou chauve-souris.
Avec près d'un millier d'espèces, c'est l'ordre de mammifères le plus nombreux
après celui des rongeurs, auquel il est parfois associé.
Ces animaux, comme les Cétacés, sont souvent capables d'écholocation.
""",
        'liens': ['http://fr.wikipedia.org/wiki/Chiroptera'],
        'tags': ['chiro', 'vigiechiro', 'ultrason']
    })
    # Then children
    child1_id = db.taxons.insert({
        'libelle_long': 'Pteropus conspicillatus)',
        'libelle_court': 'Roussette',
        'description': """D'après wikipedia :
Roussette est un nom vernaculaire ambigu en français,
pouvant désigner plusieurs espèces différentes de chauves-souris frugivores,
plus précisément parmi les Ptéropodidés, appelées aussi Flying foxes en anglais,
traduit par renards volants.
C'est le cas notamment des espèces des genres Acerodon, Pteropus et Rousettus.
""",
        'parent': parent_id,
        'liens': ['http://fr.wikipedia.org/wiki/Roussette_(chiropt%C3%A8re)'],
        'tags': ['chiro', 'vigiechiro', 'ultrason']
    })
    child2_id = db.taxons.insert({
        'libelle_long': 'Megadermatidae)',
        'libelle_court': 'faux-vampires',
        'description': """D'après wikipedia :
Les mégadermatidés (Megadermatidae) sont une famille de chiroptères du sous-ordre
des Yinpterochiroptera. C'est la famille des « faux-vampires ».
Cette espèce vit en Afrique. On a longtemps cru qu’elle se nourrissait de sang.
""",
        'parent': parent_id,
        'liens': ['http://fr.wikipedia.org/wiki/Megadermatidae'],
        'tags': ['chiro', 'vigiechiro', 'ultrason']
    })
    def finalizer():
        for taxon_id in [parent_id, child1_id, child2_id]:
            db.taxons.remove({'_id': taxon_id})
    request.addfinalizer(finalizer)
    return db.taxons.find()


def test_access(taxons_base, administrateur):
    r = administrateur.get('/taxons')
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 3


@pytest.mark.xfail
def test_circular_parent(taxons_base, administrateur):
    url = '/taxons/{}'.format(taxons_base[0]['_id'])
    r = administrateur.get(url)
    r = administrateur.patch(url, headers={'If-Match': r.json()['_etag']},
                             json={"parent": str(taxons_base[1]['_id'])})
    assert r.status_code == 400
