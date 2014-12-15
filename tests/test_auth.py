import requests
from scille_nature_api import settings

def test_allowed():
	assert requests.get(settings.BACKEND_DOMAIN).status_code == 401

if __name__ == '__main__':
	test_allowed()
