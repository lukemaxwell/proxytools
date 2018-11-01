# -*- coding: utf-8 -*-
"""
Proxy class module.
"""
import yarl

from .whois import WHOIS, WHOISError


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

    @staticmethod
    def from_string(url):
        """
        Static method to return proxy from url string.
        """
        url = yarl.URL(url)
        return Proxy(host=url.host, port=url.port, scheme=url.scheme)

    def country(self):
        """
        Return proxy host country from WHOIS lookup.

        :returns: str
        :raises: proxytools.whois.WHOISError
        """
        response = WHOIS().get(self.host)
        try:
            return response['country']
        except KeyError:
            raise WHOISError('Could not obtain country')

    def as_dict(self, inc_country=False):
        """
        Return dictionary representation of object.

        :returns: dict
        """
        data = {
            'host': self.host,
            'port': self.port
        }

        if inc_country:
            data['country'] = self.country()

        return data
