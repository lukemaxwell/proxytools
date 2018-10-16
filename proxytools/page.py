"""
Module for Page class.
"""
from .parser import ProxyParser, ParserError


class Page:
    url = None
    html = None

    def __init__(self, url, html):
        """
        :param url: the page URL
        :param html: the page html
        :type url: yarl.URL
        :type html: str
        """
        self.url = url
        self.html = html
        self.parser = ProxyParser()

    def contains_ips(self):
        """
        Returns True if page html contains more than one IP address.

        :returns: bool
        """
        ips = self.parser.parse_ips_with_regex(self.html)

        if len(ips) > 1:
            return True
        else:
            return False

    def proxies(self):
        """
        Return list of proxies extracted from page.

        :returns: list
        """
        try:
            proxies = self.parser.parse_proxies(self.html)
        except ParserError:
            proxies = []
        return proxies


    def as_dict(self):
        """
        Return dictionary representation of object.

        :returns: dict
        """
        return {
            'url': str(self.url),
            'html': self.html
        }

