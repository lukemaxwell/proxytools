# -*- coding: utf-8 -*-
"""
Parser module.
"""
import inscriptis
import ipaddress
import logging
import pandas
import re
import sys
# Proxytools
from .proxy import Proxy

# Module vars
_logger = logging.getLogger(__name__)


# Custom exceptions
class ParserError(Exception):
    ''' Generic parser exception. '''


class ColumnNotFound(Exception):
    ''' Parser did not find column in pandas DataFrame. '''


class PortNotFound(Exception):
    ''' Could not parse port. '''


class IPNotFound(Exception):
    ''' Could not parse IP. '''


class ProxyParser():
    def __init__(self):
        self.ip_host_regex = r'([0-9]+(?:\.[0-9]+){3})+(\s*:\s*[0-9]{1,5})?'
        self.ip_regex = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'

    def _format_regex_results(self, matches):
        """
        Clean results from self.ip_host_regex search.
        :param matches: list of regex matches
        :type matches: list
        :returns: list
        """
        cleaned = []
        for match in matches:
            host = match[0].replace(' ', '').replace('\t', '')
            port = match[1].replace(' ', '').replace('\t', '')
            cleaned.append((host, port))
        return cleaned

    def parse_ips_with_regex(self, html):
        """
        Extract IP addresses from `html` with regex.

        :param html: the HTML
        :type html: str
        :returns: list
        """
        text = inscriptis.get_text(html)
        matches = re.findall(self.ip_regex, text)
        ips = [m.replace(' ', '').replace('\t', '') for m in matches]
        return ips

    def parse_proxies_with_regex(self, html):
        """
        Extract proxies from `html` using regex.

        :param html: the HTML
        :type html: str
        :returns: proxytools.Proxy
        :raises: ParserError
        """
        text = inscriptis.get_text(html)
        matches = re.findall(self.ip_host_regex, text)
        matches = self._format_regex_results(matches)
        proxies = []
        for match in matches:
            try:
                proxy = Proxy(host=match[0], port=match[1])
                proxies.append(proxy)
            except ValueError:
                raise ParserError('Could not parse proxies with regex')
        return proxies

    def get_host_column_from_df(self, df):
        """
        Search dataframe `df` for "Host" column.

        Returns index of column or raises ColumnNotFound.

        :param df: dataframe to search
        :type df: pandas.DataFrame
        :returns: int
        :raises: ColumnNotFound
        """
        columns = [str(c).lower() for c in df.columns.values.tolist()]

        try:
            return columns.index('ip address')
        except ValueError:
            pass

        try:
            return columns.index('ip')
        except ValueError:
            pass

        try:
            return columns.index('host')
        except ValueError:
            pass

        raise ColumnNotFound('Could not get IP column')

    def get_port_column_from_df(self, df):
        """
        Return column index of "port" column

        :returns: int
        :raises: ColumnNotFound
        """
        columns = [str(c).lower() for c in df.columns.values.tolist()]

        try:
            return columns.index('port')
        except ValueError:
            raise ColumnNotFound('Could not get port column')

    def parse_proxies_with_pandas(self, html):
        """
        Extract proxies from html using Pandas.

        :param html: the HTML string
        :type html: str
        :returns: list
        :raises: ParserError
        """
        proxies = []
        try:
            dfs = pandas.read_html(html)
        except ValueError:
            # No tables found
            raise ParserError('Could not extract proxies with pandas, no tables found')

        for df in dfs:
            host_col = None
            port_col = None
            proxy = None

            # Attempt to locate Host and Port columns
            try:
                host_col = self.get_host_column_from_df(df)
            except ColumnNotFound:
                raise ParserError('Could not parse host column')

            try:
                port_col = self.get_port_column_from_df(df)
            except ColumnNotFound:
                raise ParserError('Could not parse port column')

            # Extract the proxies
            for idx, row in df.iterrows():
                host = str(row[host_col]).strip()
                try:
                    host = self.parse_ip(row[host_col])
                except IPNotFound:
                    continue

                try:
                    port = self.parse_port(row[port_col])
                except PortNotFound:
                    continue

                proxy = Proxy(host=host, port=port)
                proxies.append(proxy)

            return proxies


    def parse_port(self, val):
        """
        Parse proxy port from `val`.

        :param val: the val to parse port from

        :returns: int
        """
        if isinstance(val, float):
            try:
                return int(round(val))
            except ValueError:
                pass
        elif isinstance(val, str):
            val = val.strip()
            try:
                return int(val)
            except:
                pass

        _logger.debug('Could not parse port from: {}'.format(val))
        raise PortNotFound('Could not parse port')

    def parse_ip(self, val):
        """
        Parse proxy IP from `val`.

        :param text: the text to parse
        :returns: str
        """
        try:
            text = str(val)
        except TypeError:
            _logger.debug('Could not extract ip from text: {}'.format(text))
            raise IPNotFound('Could not parse IP')

        matches = re.findall(self.ip_regex, text)
        ips = [m.replace(' ', '').replace('\t', '') for m in matches]
        # Assume there is only one
        try:
            return ips[0]
        except IndexError:
            _logger.debug('Could not extract ip from text: {}'.format(text))
            raise IPNotFound('Could not parse IP')

    def parse_proxies(self, html):
        """
        Extract proxies from `html`.

        :param html: the HTML
        :type html: str
        :returns: list
        :raises: ParserError
        """
        # Try regex first
        try:
            return self.parse_proxies_with_regex(html)
        except ParserError:
            pass

        _logger.info('Regex parsing failed, attempting extraction with Pandas')

        # Try pandas
        try:
            return  self.parse_proxies_with_pandas(html)
        except ParserError:
            pass

        raise ParserError('Could not parse proxies with either regex or Pandas')
