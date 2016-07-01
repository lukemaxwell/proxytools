#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import logging
from tornado import ioloop, queues

from .proxytools import (get_proxy_status, get_url_status_with_proxy, process_items,
                         get_proxies_from_url,
                         google_search_proxies, ping_proxy)



CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option('--log-level', 
              help='Set log level.',
              default='info',
              type=click.Choice(['debug', 'info', 'warning', 'error', 'critical']))
def cli(log_level):
    log_levels = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }
    logging.basicConfig(level=log_levels[log_level])


@cli.command()
@click.option('--timeout',
              '-t',
              type=click.INT,
              default=10,
              help='http connect timout (default: 10)')
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=100,
              help="concurrent http requests (default: 100)")
@click.option('--input-file',
              '-i',
              type=click.Path(exists=True),
              help="file containing a list of proxies")
@click.option('--proxy',
              '-p',
              help='proxy url in format PROTOCOL://USERNAME:PASSWORD@HOST:PORT')
@click.argument('url', type=click.STRING)
@click.pass_context
def test_with_url(ctx, input_file, proxy, url, timeout, concurrency):
    '''
    Test proxies work with URL.
    \b
    Proxies should be in format PROTOCOL://USERNAME:PASSWORD@HOST:PORT.
    '''
    if input_file is not None:
        with open(input_file) as f:
            proxies = f.read().splitlines()
    elif proxy is not None:
        proxies = [proxy]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --proxy', ctx)

    process_items(get_url_status_with_proxy,
                  items=proxies,
                  url='https://www.google.com',
                  timeout=timeout,
                  concurrency=concurrency)


@cli.command()
@click.option('--input-file',
              '-i',
              type=click.Path(exists=True),
              help="file containing a list of urls")
@click.option('--url', '-u', type=click.STRING)
@click.pass_context
def extract(ctx, input_file, url):
    '''
    Extract proxies from URLs.
    '''
    if input_file is not None:
        with open(input_file) as f:
            urls = f.read().splitlines()
    elif url is not None:
        urls = [url]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --url', ctx)

    process_items(get_proxies_from_url, items=urls)


@cli.command()
@click.option('--timeout',
              '-t',
              type=click.INT,
              default=10,
              help='http connect timout (default: 10)')
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=100,
              help="concurrent http requests (default: 100)")
@click.option('--input-file',
              '-i',
              type=click.File(),
              help="file containing a list of urls")
@click.option('--proxy', '-p', type=click.STRING)
@click.pass_context
def test_with_http(ctx, input_file, proxy, timeout, concurrency):
    '''
    Test proxy responds to http connection.
    '''
    if input_file is not None:
        proxies = input_file.read().splitlines()
    elif proxy is not None:
        proxies = [proxy]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --proxy', ctx)

    process_items(get_proxy_status, items=proxies, timeout=timeout, concurrency=concurrency)


@cli.command()
@click.option('--timeout',
              '-t',
              type=click.INT,
              default=2,
              help="ping timout (default: {})".format(2))
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=100,
              help="concurrent ping requests (default: {})".format(100))
@click.option('--input-file',
              '-i',
              type=click.File(),
              help="file containing a list of urls")
@click.option('--proxy', '-p', type=click.STRING)
@click.pass_context
def test_with_ping(ctx, input_file, proxy, timeout, concurrency):
    '''
    Test proxy responds to ping.
    '''
    if input_file is not None:
        proxies = input_file.read().splitlines()
    elif proxy is not None:
        proxies = [proxy]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --proxy', ctx)

    process_items(ping_proxy, items=proxies, timeout=timeout, concurrency=concurrency)


@cli.command()
@click.pass_context
def search_sources(ctx):
    '''
    Find URLs containing proxies.
    '''
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(google_search_proxies)


if __name__ == '__main__':
    cli()
