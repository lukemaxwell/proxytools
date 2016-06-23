# -*- coding: utf-8 -*-
import re
from lxml import html as ht


class ParseException(Exception):
    ''' Represents a user-facing exception. '''
    def __init__(self, message):
        self.message = message


class GoogleParser():
    def __init__(self):
        self.link_xpath = "//div[@class='g']//h3/a/@href"

    def get_links(self, html_string):
        html_doc = ht.document_fromstring(html_string)
        links = html_doc.xpath(self.link_xpath)
        cleaned_links = []

        for link in links:
            # Ignore image links that are mixed in with standard results
            if not link.startswith('/images?q='):
                # Strip random chars from Google links
                if link.startswith('/url?q='):
                    q = link.index('?q=')
                    sa = link.index('&sa=')
                    link = link[q+3:sa]
                cleaned_links.append(link)
        return cleaned_links


class ProxyParser():
    def __init__(self):
        self.regex = r'([0-9]+(?:\.[0-9]+){3})+(\s*:\s*[0-9]{1,5})?'

    def get_proxies(self, html_string):
        proxies = re.findall(self.regex, html_string)
        proxies = self.clean_proxies(proxies)
        return proxies

    def clean_proxies(self, proxies):
        cleaned = []
        for proxy in proxies:
            proxy = '%s%s' % (proxy[0].replace(' ', '').replace('\t', ''), proxy[1].replace(' ', '').replace('\t', ''))
            cleaned.append(proxy)
        return cleaned


class PingParser():
    def __init__(self):
        self.regex = r'^.*([0-9]+) packets transmitted, ([0-9]+) received.*$'

    def parse(self, ping_response):
        ping_response = ping_response.replace('\n', '')
        matches = re.match(self.regex, ping_response, re.I)
        result = {}
        if matches:
            sent = int(matches.groups()[0])
            received = int(matches.groups()[1])
            lost = sent - received
            result = {'sent': sent, 'received': received, 'lost': lost}
        return result

