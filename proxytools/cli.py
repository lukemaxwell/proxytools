# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""
Proxytools command line client module.
"""
import click
import json
import logging
import os
import time

import proxytools

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
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def parse(input_file, url, timeout, headless, bin_path, chrome_args):
    """
    Parse proxies from file or URL
    """
    parser = proxytools.parser.ProxyParser()
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    chrome_args = _args

    if input_file:
        html = html_file.read()
        proxies = [str(p) for p in parser.parse_proxies(html)]
    elif url:
        client = proxytools.Client()
        try:
            page = client.get_pages(
                [url], timeout=timeout, headless=headless, bin_path=bin_path, chrome_args=chrome_args)[0]
            proxies = [str(p) for p in parser.parse_proxies(page.html)]
        except IndexError:
            raise CliError('Could not get page')
    else:
        raise CliError('Supply --input-file or --url')

    print(json.dumps(proxies, indent=4))


@cli.command()
@click.option('--headless/--no-headless', default=True)
@click.option('--num', '-n',  help='number of sources to get [1-100]', default=10)
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def sources(headless, num, bin_path, chrome_args):
    """
    Search Google for proxy sources
    """
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    chrome_args = _args
    client = proxytools.Client()
    urls = client.get_source_urls(headless=headless, num=num, bin_path=bin_path, chrome_args=chrome_args)
    print(json.dumps(urls, indent=4))


@cli.command()
@click.option('--source-num', '-n',  help='number of sources to get from Google [1-100]',
              default=10)
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def search(source_num, bin_path, chrome_args):
    """
    Scrape proxies from the web
    """
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    chrome_args = _args
    client = proxytools.Client()
    proxies = client.search_proxies(source_num=source_num, bin_path=bin_path, chrome_args=chrome_args)
    urls = [str(p) for p in proxies]
    print(json.dumps(urls, indent=4))


@cli.command()
@click.argument('proxy', type=click.STRING)
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--browser-concurrency',  help='number of concurrent browser sessions', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def test(proxy, url, headless, browser_concurrency, selector, bin_path, chrome_args):
    """
    Test a proxy for a given URL
    """
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    client = proxytools.Client()
    results = client.test_proxies([proxy], url, headless=headless, browser_concurrency=browser_concurrency, selector=selector)
    print(json.dumps(results, indent=4))


@cli.command()
@click.argument('json-file', type=click.File('r'))
@click.argument('url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--browser-concurrency',  help='number of concurrent browser sessions', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def test_from_file(json_file, url, headless, browser_concurrency, selector, bin_path, chrome_args):
    """
    Test proxies from json file for a given URL
    """
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    proxies = json.load(json_file)
    client = proxytools.Client()
    results = client.test_proxies(proxies,
                                  url,
                                  headless=headless,
                                  browser_concurrency=browser_concurrency,
                                  selector=selector,
                                  bin_path=bin_path,
                                  chrome_args=chrome_args)
    print(json.dumps(results, indent=4))


@cli.command()
@click.argument('test-url', type=click.STRING)
@click.option('--headless/--no-headless', default=True)
@click.option('--tab-concurrency',  help='number of concurrent browser tabs', default=1)
@click.option('--browser-concurrency',  help='number of concurrent browser sessions', default=1)
@click.option('--geo', '-g', help='perform whois country lookup for proxies', is_flag=True)
@click.option('--limit', '-l',  help='number of proxies to get', default=1)
@click.option('--selector', '-s',  help='css selector for page validation')
@click.option('--source-num', '-n',  help='number of sources to get from Google [1-100]',
              default=10)
@click.option('--bin-path',
              help='Path to chromium executuable',
              type=click.Path(exists=True))
@click.option('--chrome-args',
              help='chromium args (comma separated)',
              type=str,
              default='')
def get(test_url, headless, tab_concurrency, browser_concurrency, limit, selector, source_num, geo, bin_path, chrome_args):
    """
    Get a working proxy
    """
    chrome_args = chrome_args.split(',')
    _args = []
    for arg in chrome_args:
        if len(arg) > 0:
            if not arg.startswith('--'):
                arg = '--{}'.format(arg)
            _args.append(arg)
    client = proxytools.Client()
    results = client.get_proxies(test_url,
                                 headless=headless,
                                 tab_concurrency=tab_concurrency,
                                 browser_concurrency=browser_concurrency,
                                 limit=limit,
                                 selector=selector,
                                 source_num=source_num,
                                 bin_path=bin_path,
                                 chrome_args=chrome_args)
    if geo:
        wait = 1  #  seconds between WHOIS request
        for result in results:
            proxy = proxytools.proxy.Proxy.from_string(result['proxy'])
            country = proxy.country()
            result['country'] = country
            time.sleep(wait)
    print(json.dumps(results, indent=4))


if __name__ == '__main__':
    cli()
