# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""
Proxytools command line client module.
"""
import click
import json
import logging
import os

import proxytools
from proxytools.parser import ProxyParser

_log_levels = [
    'NOTSET',
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
]

####################
## Command Groups ##
####################

@click.group()
@click.option('--log-level',  type=click.Choice(_log_levels), default='WARNING')
def cli(log_level):
    # Configure logging
    level = logging.getLevelName(log_level)
    logging.basicConfig(level=level)
    _logger = logging.getLogger(__name__)


##############
## Commands ##
##############

@cli.command()
@click.argument('html_file', type=click.File('r'))
def parse_proxies(html_file):
    """
    Parse proxies from file
    """
    html = html_file.read()
    parser = ProxyParser()
    proxies = [str(p) for p in parser.parse_proxies(html)]
    print(json.dumps(proxies, indent=4))


@cli.command()
def get_sources():
    """
    Search Google for proxy sources
    """
    client = proxytools.Client()
    urls = client.get_source_urls()
    print(json.dumps(urls, indent=4))


@cli.command()
def get_proxies():
    """
    Scrape proxies from the web
    """
    client = proxytools.Client()
    proxies = client.get_proxies()
    urls = [str(p) for p in proxies]
    print(json.dumps(urls, indent=4))


@cli.command()
@click.argument('proxy', type=click.STRING)
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--concurrency', '-c',  help='number of concurrent browser sessions', default=1)
def test(proxy, url, headless, concurrency):
    """
    Test a proxy for a given URL.
    """
    client = proxytools.Client()
    results = client.test_proxies([proxy], url, headless=headless, concurrency=concurrency)
    print(json.dumps(results, indent=4))


@cli.command()
@click.argument('json-file', type=click.File('r'))
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--concurrency', '-c',  help='number of concurrent browser sessions', default=1)
def test_from_file(json_file, url, headless, concurrency):
    """
    Test proxies for a given URL.
    """
    proxies = json.load(json_file)
    client = proxytools.Client()
    results = client.test_proxies(proxies, url, headless=headless, concurrency=concurrency)
    print(json.dumps(results, indent=4))


if __name__ == '__main__':
    cli()
