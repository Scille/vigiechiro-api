#!/usr/bin/env python3

from setuptools import setup, find_packages

import vigiechiro

setup(

    name='vigiechiro',
    version=vigiechiro.__version__,

    # Use custom Eve (using dev branch) and Authomatics (custom
    # python3 port) packages
    packages=["vigiechiro", "eve", "authomatic"],
    author="Scille SAS",
    author_email="contact@scille.eu",
    description="Projet viginature du Museum national d'histoire naturelle",
    long_description=open('README.md').read(),
    install_requires=[
        # Eve==0.5 (not available for the moment)
        # Eve's depandancies
        "Cerberus==0.7.2",
        "Events==0.2.1",
        "Flask-PyMongo==0.3.0",
        "Flask==0.10.1",
        "itsdangerous==0.24",
        "Jinja2==2.7.3",
        "MarkupSafe==0.23",
        "pymongo==2.7.1",
        "simplejson==3.5.3",
        "Werkzeug==0.9.6",
        "redis",
        # authomatic (not available for the moment for Python3)
        # authomatic's dependancies
        "six"
    ],

    # Add non-python files with MANIFEST.in
    # include_package_data=True,

    url='http://github.com/scille/vigiechiro-api',
    classifiers=[
        "Programming Language :: Python",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)"
        "Natural Language :: French",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ]
)
