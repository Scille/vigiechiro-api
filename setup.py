#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(

    name='vigiechiro',
    packages=find_packages(),
    author="Scille SAS",
    author_email="contact@scille.eu",
    description="Projet viginature du Museum national d'histoire naturelle",
    long_description=open('README.md').read(),
    # Eve 0.5 is not yet available
    install_requires=[
        "Eve==0.4",
        "redis",
        # authomatic (not available for the moment for Python3)
        # authomatic's dependancies
        "six"
    ],
    tests_require=[
        "pytest",
        "requests"
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
