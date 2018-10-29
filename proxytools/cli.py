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
#from .parser import ProxyParser

_log_levels = [
    'NOTSET',
    'DEBUG',
    'INFO',
    'WARNING',
    'ERROR',
    'CRITICAL'
]
_logger = logging.getLogger(__name__)


class CliError(Exception):
    pass


####################
## Command Groups ##
####################

@click.group()
@click.option('--log-level',  type=click.Choice(_log_levels), default='WARNING', envvar='LOG_LEVEL')
def cli(log_level):
    # Configure logging
    level = logging.getLevelName(log_level)
    logging.basicConfig(level=level)


##############
## Commands ##
##############

@cli.command()
@click.option('--input-file', '-f',  type=click.File('r'))
@click.option('--url', '-u',  type=click.STRING)
@click.option('--timeout', '-t',  type=click.INT, default=10)
@click.option('--headless/--no-headless', default=True)
def parse(input_file, url, timeout, headless):
    """
    Parse proxies from file or URL
    """
    parser = proxytools.parser.ProxyParser()
    if input_file:
        html = html_file.read()
        proxies = [str(p) for p in parser.parse_proxies(html)]
    elif url:
        client = proxytools.Client()
        try:
            page = client.get_pages([url], timeout=timeout, headless=headless)[0]
            proxies = [str(p) for p in parser.parse_proxies(page.html)]
        except IndexError:
            raise CliError('Could not get page')
    else:
        raise CliError('Supply --input-file or --url')

    print(json.dumps(proxies, indent=4))


@cli.command()
@click.option('--headless/--no-headless', default=True)
@click.option('--num', '-n',  help='number of sources to get [1-100]', default=10)
def sources(headless, num):
    """
    Search Google for proxy sources
    """
    client = proxytools.Client()
    urls = client.get_source_urls(headless=headless, num=num)
    print(json.dumps(urls, indent=4))


@cli.command()
@click.option('--source-num', '-n',  help='number of sources to get from Google [1-100]',
              default=10)
def search(source_num):
    """
    Scrape proxies from the web
    """
    client = proxytools.Client()
    proxies = client.search_proxies(source_num=source_num)
    urls = [str(p) for p in proxies]
    print(json.dumps(urls, indent=4))


@cli.command()
@click.argument('proxy', type=click.STRING)
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--concurrency', '-c',  help='number of concurrent browser sessions', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
def test(proxy, url, headless, concurrency, selector):
    """
    Test a proxy for a given URL
    """
    client = proxytools.Client()
    results = client.test_proxies([proxy], url, headless=headless, concurrency=concurrency, selector=selector)
    print(json.dumps(results, indent=4))


@cli.command()
@click.argument('json-file', type=click.File('r'))
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--concurrency', '-c',  help='number of concurrent browser sessions', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
def test_from_file(json_file, url, headless, concurrency, selector):
    """
    Test proxies from json file for a given URL
    """
    proxies = json.load(json_file)
    client = proxytools.Client()
    results = client.test_proxies(proxies, url, headless=headless, concurrency=concurrency, selector=selector)
    print(json.dumps(results, indent=4))


@cli.command()
@click.argument('test-url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--concurrency', '-c',  help='number of concurrent browser sessions', default=1)
@click.option('--limit', '-l',  help='number of proxies to get', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
@click.option('--source-num', '-n',  help='number of sources to get from Google [1-100]',
              default=10)
def get(test_url, headless, concurrency, limit, selector, source_num):
    """
    Get a working proxy
    """
    client = proxytools.Client()
    results = client.get_proxies(test_url, headless=headless,
                                 concurrency=concurrency, limit=limit,
                                 selector=selector, source_num=source_num)
    print(json.dumps(results, indent=4))


if __name__ == '__main__':
    cli()
