# coding=utf-8
# Created 2014 by Janusz Skonieczny 


def _load_backends():
    from keyring.backend import _load_backend
    "ensure that all keyring backends are loaded"
    backends = ('file', 'Gnome', 'Google', 'keyczar', 'multi', 'OS_X', 'pyfs', 'SecretService', 'Windows')
    list(map(_load_backend, backends))

import keyring.backend
keyring.backend._load_backends = _load_backends
