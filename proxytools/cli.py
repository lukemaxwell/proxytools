#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
from tornado import ioloop, queues
import logging

from .proxytools import (get_url_status, process_items,
                         process_tcp_items, get_proxies_from_url,
                         google_search_proxies, tcp_connect_ok)


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
@click.option('--input-file',
              '-i',
              type=click.Path(exists=True),
              help="file containing a list of proxies")
@click.option('--proxy',
              '-p',
              help='proxy url in format PROTOCOL://USERNAME:PASSWORD@HOST:PORT')
@click.argument('url', type=click.STRING)
@click.pass_context
def test_with_url(ctx, input_file, proxy, url, concurrency=100):
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

    process_items(get_url_status, items=proxies, url='https://www.google.com')


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
              help='tcp connect timout (default: 10)')
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=100,
              help="concurrent ping requests (default: 100)")
@click.option('--input-file',
              '-i',
              type=click.File(),
              help="file containing a list of urls")
@click.option('--proxy', '-p', type=click.STRING)
@click.pass_context
def test_connect(ctx, input_file, proxy, timeout, concurrency):
    '''
    Test proxy ports are open.
    '''
    if input_file is not None:
        proxies = input_file.read().splitlines()
    elif proxy is not None:
        proxies = [proxy]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --proxy', ctx)

    process_tcp_items(tcp_connect_ok, items=proxies)


@cli.command()
@click.pass_context
def search_sources(ctx):
    '''
    Find web pages containing proxies.
    '''
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(google_search_proxies)


if __name__ == '__main__':
    cli()
