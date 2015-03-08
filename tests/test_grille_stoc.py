import pytest

from .common import db, observateur


@pytest.fixture
def clean_grille_stoc(request):
    def finalizer():
        db.grille_stoc.remove()
    request.addfinalizer(finalizer)


@pytest.fixture
def grille_stoc(request=None):
    grille = [
        {"centre" : {"type" : "Point", "coordinates" : [2.551195605, 51.0423964]}, "numero" : "590017"},
        {"centre" : {"type" : "Point", "coordinates" : [2.181529126, 51.0245531]}, "numero" : "590018"},
        {"centre" : {"type" : "Point", "coordinates" : [2.209959021, 51.02458538]}, "numero" : "590019"},
        {"centre" : {"type" : "Point", "coordinates" : [2.238388948, 51.02461118]}, "numero" : "590020"},
        {"centre" : {"type" : "Point", "coordinates" : [2.266818902, 51.0246305]}, "numero" : "590021"}
    ]
    for cell in grille:
        db.grille_stoc.insert(cell)
    def finalizer():
        db.grille_stoc.remove()
    if request:
        request.addfinalizer(finalizer)
    return grille


def test_grille_lookup(observateur, grille_stoc):
    r = observateur.get('/grille_stoc/rectangle', params={
        'sw_lng': 2.181529126, 'sw_lat': 51.024553,
        'ne_lng': 2.181529127, 'ne_lat': 51.024554
    })
    assert r.status_code == 200, r.text
    assert len(r.json()['_items']) == 1, r.json()
    cell = r.json()['_items'][0]
    # grille_stoc doesn't contain metadata
    assert '_updated' not in cell
    assert '_created' not in cell
    assert '_etag' not in cell


def test_bad_request(observateur, grille_stoc):
    # Missing params
    r = observateur.get('/grille_stoc/rectangle', params={
        'sw_lng': 2.181529126, 'sw_lat': 51.024553,
        'ne_lng': 2.181529127
    })
    assert r.status_code == 422, r.text
    # Bad params
    r = observateur.get('/grille_stoc/rectangle', params={
        'sw_lng': "2a", 'sw_lat': 51.024553,
        'ne_lng': 2.181529127, 'ne_lat': 51.024554
    })
    assert r.status_code == 422, r.text
