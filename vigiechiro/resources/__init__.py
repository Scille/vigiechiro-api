from . import donnees
from . import taxons
from . import utilisateurs

DOMAIN = {
    'utilisateurs': utilisateurs.DOMAIN,
    'taxons': taxons.DOMAIN,
    'donnees': donnees.DOMAIN
}
