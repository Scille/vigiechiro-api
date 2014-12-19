import requests
from pymongo import MongoClient
import pytest

from common import db, administrateur, observateur, eve_post_internal


@pytest.fixture
def taxons_base(request):
    # Insert parent
    parent_payload = {
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
    }
    eve_post_internal('taxons', parent_payload)
    parent_id = db.taxons.find_one({'libelle_long': parent_payload['libelle_long']})['_id']
    # Then children
    child1_payload = {
        'libelle_long': 'Pteropus conspicillatus)',
        'libelle_court': 'Roussette',
        'description': """D'après wikipedia :
Roussette est un nom vernaculaire ambigu en français,
pouvant désigner plusieurs espèces différentes de chauves-souris frugivores,
plus précisément parmi les Ptéropodidés, appelées aussi Flying foxes en anglais,
traduit par renards volants.
C'est le cas notamment des espèces des genres Acerodon, Pteropus et Rousettus.
""",
        'parents': [parent_id],
        'liens': ['http://fr.wikipedia.org/wiki/Roussette_(chiropt%C3%A8re)'],
        'tags': ['chiro', 'vigiechiro', 'ultrason']
    }
    eve_post_internal('taxons', child1_payload)
    child2_payload = {
        'libelle_long': 'Megadermatidae)',
        'libelle_court': 'faux-vampires',
        'description': """D'après wikipedia :
Les mégadermatidés (Megadermatidae) sont une famille de chiroptères du sous-ordre
des Yinpterochiroptera. C'est la famille des « faux-vampires ».
Cette espèce vit en Afrique. On a longtemps cru qu’elle se nourrissait de sang.
""",
        'parents': [parent_id],
        'liens': ['http://fr.wikipedia.org/wiki/Megadermatidae'],
        'tags': ['chiro', 'vigiechiro', 'ultrason']
    }
    eve_post_internal('taxons', child2_payload)
    def finalizer():
        for payload in [parent_payload, child1_payload, child2_payload]:
            db.taxons.remove({'libelle_long': payload['libelle_long']})
    request.addfinalizer(finalizer)
    return db.taxons.find()


@pytest.fixture
def new_taxon_payload(request):
    payload = {
        'libelle_long': 'Batman',
        'parents': [],
        'liens': ['http://fr.wikipedia.org/wiki/batman'],
        'tags': ['chiro', 'vigiechiro', 'comics']
    }
    def finalizer():
        db.taxons.remove({'libelle_long': payload['libelle_long']})
    request.addfinalizer(finalizer)
    return payload


def test_access(taxons_base, observateur):
    r = observateur.get('/taxons')
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 3


def test_multi_parents(taxons_base, administrateur):
    url = '/taxons/{}'.format(taxons_base[1]['_id'])
    r = administrateur.get(url)
    assert r.status_code == 200, r.text
    payload = r.json()
    payload['parents'] = [str(taxons_base[2]['_id'])] + payload['parents']
    r = administrateur.patch(url, headers={'If-Match': payload['_etag']},
                             json={'parents': payload['parents']})
    assert r.status_code == 200, r.text
    etag = r.json()['_etag']
    # Use put instead of patch
    payload = {field: payload[field] for field in payload.keys() if not field.startswith('_')}
    r = administrateur.put(url, headers={'If-Match': etag},
                           json=payload)
    assert r.status_code == 200, r.text
    # Try with 2 times the same
    r = administrateur.get(url)
    parents = [str(taxons_base[1]['_id']) for _ in range(2)]
    r = administrateur.patch(url, headers={'If-Match': r.json()['_etag']},
                             json={'parents': parents})
    assert r.status_code == 422, r.text


def test_circular_parent(taxons_base, administrateur):
    url = '/taxons/{}'.format(taxons_base[0]['_id'])
    r = administrateur.get(url)
    assert r.status_code == 200, r.text
    r = administrateur.patch(url, headers={'If-Match': r.json()['_etag'], 'Content-type':'application/json'},
                             json={'parents': [str(taxons_base[1]['_id'])]})
    assert r.status_code == 422, r.text


def test_dummy_parent(taxons_base, new_taxon_payload, administrateur):
    url = '/taxons/{}'.format(taxons_base[0]['_id'])
    r = administrateur.get(url)
    assert r.status_code == 200, r.text
    etag = r.json()['_etag']
    # Bad ids : dummy, not existing, own's id and different resource's id
    for dummy in ['dummy', '5490237a1d41c81800d52c18',
                  str(taxons_base[0]['_id']), str(administrateur.user['_id'])]:
        r = administrateur.patch(url, headers={'If-Match': etag},
                                 json={'parents': [dummy]})
        assert r.status_code == 422, r.text
    # Check for POST too
    for dummy in ['dummy', '5490237a1d41c81800d52c18',
                  str(administrateur.user['_id'])]:
        new_taxon_payload['parents'] = [dummy]
        r = administrateur.post('/taxons', json=new_taxon_payload)
        assert r.status_code == 422, r.text


def test_modif(taxons_base, administrateur, observateur):
    url = '/taxons/{}'.format(taxons_base[0]['_id'])
    r = administrateur.get(url)
    new_tags = ['new_tag1', 'new_tag2']
    r = administrateur.patch(url, headers={'If-Match': r.json()['_etag']},
                             json={"tags": new_tags})
    r = administrateur.get(url)
    assert r.status_code == 200, r.text
    assert r.json()['tags'] == new_tags
    # Observateur cannot modify taxons
    r = observateur.patch(url, headers={'If-Match': r.json()['_etag']},
                          json={"tags": ['new_tag']})
    assert r.status_code == 401, r.text


def test_unique_libelle(taxons_base, new_taxon_payload, administrateur):
    for libelle in ['libelle_long', 'libelle_court']:
        new_taxon_payload[libelle] = taxons_base[0][libelle]
        r = administrateur.post('/taxons', json=new_taxon_payload)
        assert r.status_code == 422, r.text
