"""
Backend of the vigiechiro project
"""

__version__ = "0.1"

# Monkeypatch to fix import in flask-cache
from werkzeug.utils import import_string
import werkzeug
werkzeug.import_string = import_string

from vigiechiro.app import app
