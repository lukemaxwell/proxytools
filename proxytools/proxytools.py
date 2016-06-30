#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import collections
from datetime import timedelta
import logging
import re
import subprocess
import sys
import time
from tornado import (httpclient, tcpclient, netutil,
                     gen, ioloop, queues)

logger = logging.getLogger(__name__)

try:
    from HTMLParser import HTMLParser
    from urlparse import urljoin, urldefrag, urlencode, urlparse, urlunparse, parse_qsl
except ImportError:
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urldefrag, urlencode, urlparse, urlunparse, parse_qsl


from .parser import GoogleParser, ProxyParser, PingParser
from .ping import ping_proxies
from .tcp import tcp_connections


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:17.0) Gecko/20100101 Firefox/17.0;',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US',
    'Accept-Encoding': 'gzip, deflate',
}
CONNECT_TIMEOUT = 10
PING_TIMEOUT = 1
CONNECT_TIMEOUT = 2
TCP_TIMEOUT = 2
CONCURRENCY = 100

httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")

# Named tuple for storing proxies
Proxy = collections.namedtuple('Proxy', 'protocol username password host port')

class ProxyToolsError(Exception):
    """
    Represents a human-facing exception.
    """
    def __init__(self, message):
        self.message = message


def on_timeout():
    print("timeout")
    ioloop.IOLoop.current().stop()


def print_data(data, func):
    '''
    Print data to stdout.
    Custom print formatter for data returned by proxytools methods.
    '''
    if func ==  get_proxies_from_url:
        for proxies in data.values(): 
            print(*proxies, sep='\n')
    elif func ==  get_url_status:
        for key, val in data.items():
            print('{}: {}'.format(key, val))
    elif func == tcp_connect_ok:
        for key, val in data.items():
            print('{}: {}'.format(key, val))
    else:
        raise NotImplemented



def parse_host(proxy):
    '''
    Parse host from proxy string.
    '''
    pass


def proxy_from_string(proxy):
    '''
    Parse proxy string into named tuple.
    '''
    username = ''
    password = ''
    host = ''
    port = 80
    protocol = 'http'

    # Parse protocol
    match = re.search('http(s)?', proxy)

    try:
        protocol =  match.group(0)
    except AttributeError:
        pass # use default

    # Split the remainder into user, pass, host, port  
    fragment = proxy.replace(protocol, '')
    fragment = fragment.replace('://', '')
    parts = fragment.split('@')

    if len(parts) == 2:
        auth_parts = parts[0].split(':')
        username = auth_parts[0]

        try:
            password = auth_parts[1]
        except IndexError:
            pass # use default

        loc_parts = parts[1].split(':')
        host = loc_parts[0]

        try:
            port = loc_parts[1]
        except IndexError:
            pass # use default
    else:
        loc_parts = parts[0].split(':')
        host = loc_parts[0]

        try:
            port = loc_parts[1]
        except IndexError:
            pass # use default

    proxy = Proxy(protocol=protocol,
                  host=host,
                  port=port,
                  username=username,
                  password=password)
    return proxy

    


@gen.coroutine
def tcp_connect_ok(proxy_string, client, timeout_seconds=1):
    '''
    Attempt TCP connection.
    '''
    proxy = proxy_from_string(proxy_string)
    try:
        connect = yield gen.with_timeout(timedelta(seconds=timeout_seconds),
                client.connect(host=proxy.host, port=proxy.port))
        raise gen.Return(True)
    except:
        raise gen.Return(False)


@gen.coroutine
def get_links_from_url(url):
    """Download the page at `url` and parse it for links.

    Returned links have had the fragment after `#` removed, and have been made
    absolute so, e.g. the URL 'gen.html#tornado.gen.coroutine' becomes
    'http://www.tornadoweb.org/en/stable/gen.html'.
    """
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url, validate_cert=False)
        logger.debug('fetched %s' % url)

        html = response.body if isinstance(response.body, str) \
            else response.body.decode()
        urls = [urljoin(url, remove_fragment(new_url))
                for new_url in get_links(html)]
    except Exception as e:
        print('Exception: %s %s' % (e, url))
        raise gen.Return([])

    raise gen.Return(urls)


@gen.coroutine
def get_proxies_from_url(url):
    """Download the page at `url` and parse it for proxies.
    """
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                            headers=HEADERS,
                                                            connect_timeout=CONNECT_TIMEOUT,
                                                            validate_cert=False)
        logger.debug('fetched %s' % url)

        body = response.body if isinstance(response.body, str) \
            else response.body.decode()
        parser = ProxyParser()
        proxies = parser.get_proxies(body)
    except Exception as e:
        logger.debug('Exception: %s %s' % (e, url))
        raise gen.Return([])

    raise gen.Return(proxies)


@gen.coroutine
def get_google_results(query, base_url='https://www.google.co.uk/search', num_results=100, start=1):
    """Download the google results at `url` and parse it for links.
    """
    params =  {
        'q': query,
        'num': num_results,
        'start': start
    }
    url = add_params_to_url(base_url, params)
    parser = GoogleParser()
    logger.debug('Fetching {}'.format(url))
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                            headers=HEADERS,
                                                            validate_cert=False )

        logger.debug('Response: {}'.format(response.code))
        html = response.body if isinstance(response.body, str) \
            else response.body.decode()
        #urls = [urljoin(url, remove_fragment(new_url))
        #        for new_url in get_google_result_links(html)]
        urls = parser.get_links(html)
    except Exception as e:
        print('Exception: %s %s' % (e, url))
        raise gen.Return([])

    raise gen.Return(urls)


def add_params_to_url(url, params):
    url_parts = list(urlparse(url))
    query = dict(parse_qsl(url_parts[4]))
    query.update(params)

    url_parts[4] = urlencode(query)

    return urlunparse(url_parts)

def remove_fragment(url):
    pure_url, frag = urldefrag(url)
    return pure_url


def get_links(html):
    class URLSeeker(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.urls = []

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get('href')
            if href and tag == 'a':
                self.urls.append(href)

    url_seeker = URLSeeker()
    url_seeker.feed(html)
    return url_seeker.urls


def get_google_result_links(html):
    class URLSeeker(HTMLParser):
        def __init__(self):
            HTMLParser.__init__(self)
            self.urls = []

        def handle_starttag(self, tag, attrs):
            href = dict(attrs).get('href')
            if href and tag == 'a':
                self.urls.append(href)

    url_seeker = URLSeeker()
    url_seeker.feed(html)
    return url_seeker.urls


@gen.coroutine
def get_proxies_from_urls(urls, output_file=None):
    q = queues.Queue()
    start = time.time()
    fetching, fetched = set(), set()
    all_proxies = set()

    @gen.coroutine
    def fetch_url():
        current_url = yield q.get()
        try:
            if current_url in fetching:
                return

            print('fetching %s' % current_url)
            fetching.add(current_url)
            proxies = yield get_proxies_from_url(current_url)
            for proxy in proxies:
                all_proxies.add(proxy)
            fetched.add(current_url)

        finally:
            q.task_done()

    @gen.coroutine
    def worker():
        while True:
            yield fetch_url()

    for url in urls:
        q.put(url)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(CONCURRENCY):
        worker()
    yield q.join(timeout=timedelta(seconds=300))
    assert fetching == fetched
    print('Done in %d seconds, fetched %s URLs. found %s proxies.' % (
        time.time() - start, len(fetched), len(all_proxies)))

    all_proxies = set(all_proxies)

    if output_file is not None:
        with open(output_file, 'w+') as f:
            f.write('\n'.join(all_proxies))


@gen.coroutine
def get_url_status(proxy, url, timeout=5):
    proxy_parts = proxy.split(':')
    proxy_host = 'http://{}'.format(proxy_parts[0])

    if len(proxy_parts) == 2:
        proxy_port = int(proxy_parts[1])
    else:
        proxy_port = 80

    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                            headers=HEADERS,
                                                            proxy_host=proxy_host,
                                                            proxy_port=proxy_port,
                                                            request_timeout=timeout,
                                                            validate_cert=False )
        code = response.code 
    except httpclient.HTTPError as e:
        code = e

    raise gen.Return(code)


@gen.coroutine
def producer(items, q):
    for item in items:
        yield q.put(item)


@gen.coroutine
def consumer(q, processing, func, *args, **kwargs):
    while True:
        item = yield q.get()
        if item not in processing:
            processing.add(item)
            try:
                logger.debug('Processing %s' % item)
                results = yield func(item, *args, **kwargs) 
                data = {item: results}
                print_data(data, func)
                raise gen.Return(results)
            finally:
                q.task_done()
                processing.remove(item)


@gen.coroutine
def process_items(func, items, concurrency=100, *args, **kwargs):
    q = queues.Queue()
    processing = set()
    producer(items, q)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(concurrency):
        consumer(q, processing, func, *args, **kwargs)

    loop = ioloop.IOLoop.current()

    def stop(future):
            loop.stop()
            future.result()  # Raise error if there is one

    # Wait for consumer to finish all tasks
    q.join().add_done_callback(stop)
    loop.start()


@gen.coroutine
def process_tcp_items(func, items, concurrency=100, *args, **kwargs):
    q = queues.Queue()
    processing = set()
    producer(items, q)
    netutil.Resolver.configure('tornado.netutil.ThreadedResolver')
    loop = ioloop.IOLoop.current()
    resolver = netutil.Resolver(io_loop=loop)
    client = tcpclient.TCPClient(resolver=resolver)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(concurrency):
        consumer(q, processing, func, client=client, *args, **kwargs)

    def stop(future):
            loop.stop()
            client.close()
            future.result()  # Raise error if there is one

    # Wait for consumer to finish all tasks
    q.join().add_done_callback(stop)
    loop.start()

@gen.coroutine
def test_proxies_with_url(proxies, url):
    q = queues.Queue()
    start = time.time()
    fetching, fetched = set(), set()
    working_proxies = set()
    results = set()

    @gen.coroutine
    def test_proxy():
        current_proxy = yield q.get()
        try:
            if current_proxy in fetching:
                return

            proxy_parts = current_proxy.split(':')
            proxy_host = 'http://{}'.format(proxy_parts[0])

            if len(proxy_parts) == 2:
                proxy_port = int(proxy_parts[1])
            else:
                proxy_port = 80

            print('fetching with %s:%s' % (proxy_host, proxy_port))
            fetching.add(current_proxy)
            try:
                response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                                    headers=HEADERS,
                                                                    proxy_host=proxy_host,
                                                                    proxy_port=proxy_port,
                                                                    request_timeout=5,
                                                                    validate_cert=False )
                results.add((current_proxy, response.code))
                working_proxies.add(current_proxy)
                print('{} OK'.format(current_proxy))
            except httpclient.HTTPError as e:
                print(e)
                results.add((current_proxy, e)) # Gateway Timeout

            fetched.add(current_proxy)

        finally:
            q.task_done()

    @gen.coroutine
    def worker():
        while True:
            yield test_proxy()

    for proxy in proxies:
        q.put(proxy)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(CONCURRENCY):
        worker()

    yield q.join(timeout=timedelta(seconds=300))
    assert fetching == fetched
    print('Done in %d seconds, fetched %s URLs. Found %s proxies, discarded %s proxies.' % (
        time.time() - start, len(fetched), len(working_proxies), len(proxies) - len(working_proxies)))


@gen.coroutine
def google_search_proxies():
    logger.debug('Searching google...')
    query = '+":8080" +":3128" +":80" filetype:txt'
    urls = yield get_google_results(query)
    print(*urls,sep='\n')
    raise gen.Return(urls)


CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])
@click.group(context_settings=CONTEXT_SETTINGS)
def cli():
    pass


@cli.command()
@click.argument('output', type=click.Path())
def search_sources(output):
    '''
    Find web pages containing proxies.
    '''
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(lambda: google_search_proxies(output))


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
def test_url(ctx, input_file, proxy, url):
    '''
    Test proxies work for URL.
    '''
    if input_file is not None:
        with open(input_file) as f:
            proxies = f.read().splitlines()
    elif proxy is not None:
        proxies = [proxy]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --proxy', ctx)

    io_loop = ioloop.IOLoop.current()
    io_loop.add_callback(lambda: print('hi'))
    io_loop.run_sync(lambda: test_proxies_with_url(proxies, url))


@cli.command()
@click.option('--timeout',
              '-t',
              type=click.INT,
              default=PING_TIMEOUT,
              help="ping timout (default: {})".format(PING_TIMEOUT))
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=CONCURRENCY,
              help="concurrent ping requests (default: {})".format(CONCURRENCY))
@click.argument('input_file', type=click.Path())
@click.argument('output_file', type=click.Path())
def test_ping(input_file, output_file, timeout, concurrency):
    '''
    Test proxy servers respond to ping.
    '''
    with open(input_file) as f:
        proxies = f.read().splitlines()

    bar = click.progressbar(length=len(proxies), label='Pinging proxies')
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(lambda: ping_proxies(proxies=proxies,
                                        output_file=output_file,
                                        concurrency=concurrency,
                                        timeout=timeout,
                                        progress_bar=bar))
    bar.finish()


@cli.command()
@click.option('--timeout',
              '-t',
              type=click.INT,
              default=CONNECT_TIMEOUT,
              help="tcp connect timout (default: {})".format(CONNECT_TIMEOUT))
@click.option('--concurrency',
              '-c',
              type=click.INT,
              default=CONCURRENCY,
              help="concurrent ping requests (default: {})".format(CONCURRENCY))
@click.argument('input_file', type=click.Path())
@click.argument('output_file', type=click.Path())
def test_connect(input_file, output_file, timeout, concurrency):
    '''
    Test proxy ports are open.
    '''
    with open(input_file) as f:
        proxies = f.read().splitlines()

    bar = click.progressbar(length=len(proxies), label='Testing ports')
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(lambda: tcp_connections(proxies=proxies,
                                        output_file=output_file,
                                        concurrency=concurrency,
                                        progress_bar=bar))
    bar.finish()


@cli.command()
@click.option('--input-file',
              '-i',
              type=click.Path(exists=True),
              help="file containing a list of urls")
@click.argument('output-file', type=click.Path())
@click.option('--url', '-u', type=click.STRING)
@click.pass_context
def scrape(ctx, input_file, url, output_file):
    '''
    Scrape proxies.
    '''
    urls = []
    if input_file is not None:
        with open(input_file) as f:
            urls = f.read().splitlines()
    elif url is not None:
        urls = [url]
    else:
        click.echo(ctx.get_help())
        raise click.exceptions.UsageError('supply --input-file or --url', ctx)

    if urls:
        io_loop = ioloop.IOLoop.current()
        io_loop.run_sync(lambda: get_proxies_from_urls(urls, output_file))

@cli.command()
def testy():
    items = [
        '92.255.172.214:8080',
        '115.127.33.186:8080',
        '179.242.77.205:8080'
    ]
    process_items(get_url_status, items=items, url='https://www.google.com')

if __name__ == '__main__':
    import logging
    logging.basicConfig()
    cli()
