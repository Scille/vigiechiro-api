from . import donnees
from . import taxons
from . import utilisateurs
from . import protocoles
from . import participations

DOMAIN = {
    'utilisateurs': utilisateurs.DOMAIN,
    'taxons': taxons.DOMAIN,
    'donnees': donnees.DOMAIN,
    'protocoles': protocoles.DOMAIN,
    'participations': participations.DOMAIN
}
