from .common import observateur


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
