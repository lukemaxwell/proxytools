# -*- coding: utf-8 -*-
"""
Proxy class module.
"""
import yarl


class Proxy:
    def __init__(self, host:str, port:int, scheme: str='http'):

        if not isinstance(port, int):
            raise ValueError('Port requires integer value')

        self.host = str(host)
        self.port = port
        self.scheme = scheme
        self.url = yarl.URL.build(scheme=self.scheme, host=self.host, port=str(self.port))

    def __str__(self):
        return str(self.url)

    def as_dict(self):
        """
        Return dictionary representation of object.

        :returns: dict
        """
        return {
            'host': self.host,
            'port': self.port
        }
