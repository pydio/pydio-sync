__author__ = 'charles'

from py.sdk import PydioSdk


class SdkTest():

    def __init__(self, url='', basepath='', ws_id='', user_id='', auth=()):
        self.sdk = PydioSdk(url, basepath, ws_id, user_id, auth)