#!/usr/bin/env python
# -*- coding: utf-8 -*-
import click
import collections
from datetime import timedelta
import logging
import json
import re
import signal
import subprocess
import sys
import time
from tornado import (httpclient, tcpclient, netutil,
                     gen, ioloop, queues, iostream, process)

try:
    from HTMLParser import HTMLParser
    from urlparse import urljoin, urldefrag, urlencode, urlparse, urlunparse, parse_qsl
except ImportError:
    from html.parser import HTMLParser
    from urllib.parse import urljoin, urldefrag, urlencode, urlparse, urlunparse, parse_qsl

from .parser import GoogleParser, ProxyParser, PingParser


### Config
logger = logging.getLogger(__name__)
#netutil.Resolver.configure('tornado.platform.caresresolver.CaresResolver')
httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
# Named tuple for storing proxies
Proxy = collections.namedtuple('Proxy', 'protocol username password host port')
# Headers used for http requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:17.0) Gecko/20100101 Firefox/17.0;',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US',
    'Accept-Encoding': 'gzip, deflate',
}
STREAM = process.Subprocess.STREAM


class ProxyToolsError(Exception):
    """
    Represents a human-facing exception.
    """
    def __init__(self, message):
        self.message = message


def print_data(data, func):
    '''
    Print data to stdout.
    Custom print formatter for data returned by proxytools methods.
    '''
    if func ==  get_proxies_from_url:
        for proxies in data.values():
            print(*proxies, sep='\n')
    else:
        for key, val in data.items():
            print('{} {}'.format(key, val))


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
            port = int(loc_parts[1])
        except IndexError:
            pass # use default
        except ValueError:
            raise ValueError('Port must be a number: {}'.format(loc_parts[1]))
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


def parse_error_code(error):
    '''
    Parse a tornado httpclient.HTTPError and return code as integer.

    Example error:
    "HTTP 599: Connection timed out after 2001 milliseconds"
    '''
    try:
        code = error.split(':')[0].split()[1]
    except IndexError:
        raise ValueError('Could not parse tornado error: {}'.format(error))
    except Exception as e:
        raise

    try:
        code = int(code)
    except:
        raise ValueError('Could not parse tornado error: {}'.format(error))

    return code


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
def get_proxies_from_url(url, timeout=5):
    """Download the page at `url` and parse it for proxies.
    """
    proxies = []
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                            headers=HEADERS,
                                                            connect_timeout=timeout,
                                                            validate_cert=False)
        logger.debug('fetched %s' % url)

        body = response.body if isinstance(response.body, str) \
            else response.body.decode()
        parser = ProxyParser()
        proxies = parser.get_proxies(body)
    except Exception as e:
        logger.debug('Exception: %s %s' % (e, url))
    finally:
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
    '''
    Safely add or update URL parameters.
    '''
    url_parts = list(urlparse(url))
    query = dict(parse_qsl(url_parts[4]))
    query.update(params)

    url_parts[4] = urlencode(query)

    return urlunparse(url_parts)


def remove_fragment(url):
    pure_url, frag = urldefrag(url)
    return pure_url


def get_links(html):
    '''
    Extract href links from html.
    '''
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
    '''
    Extract href links from Google results page.
    '''
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
def get_url_status_with_proxy(proxy, url, timeout=5):
    '''
    Fetch URL with proxy and return status code or error message.
    '''
    proxy = proxy_from_string(proxy)
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                                            headers=HEADERS,
                                                            proxy_host=proxy.host,
                                                            proxy_port=int(proxy.port),
                                                            connect_timeout=timeout,
                                                            request_timeout=timeout,
                                                            validate_cert=False)
        code = response.code
    except httpclient.HTTPError as e:
        #code = parse_error_code(str(e))
        code = str(e)
    finally:
        raise gen.Return(code)



@gen.coroutine
def get_proxy_status(proxy, timeout=5, concurrency=100):
    '''
    Fetch URL and return status code or error message.
    '''
    invalid_codes = [599]
    status = 'DOWN'
    proxy = proxy_from_string(proxy)
    url = '{}://{}:{}'.format(proxy.protocol, proxy.host, proxy.port)
    try:
        response = yield httpclient.AsyncHTTPClient().fetch(url,
                                      headers=HEADERS,
                                      request_timeout=timeout,
                                      connect_timeout=timeout,
                                      validate_cert=False)
        code = response.code
    except httpclient.HTTPError as e:
        #code = parse_error_code(str(e))
        code = str(e)
    except Exception as e:
        code = str(e)
    finally:
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
            except Exception as e:
                #print(e)
                pass
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
    signal.signal(signal.SIGINT, lambda sig, frame: loop.add_callback_from_signal(kill))

    def stop(future):
            loop.stop()
            future.result()  # Raise error if there is one

    def kill():
            loop.stop()

    # Wait for consumer to finish all tasks
    q.join().add_done_callback(stop)
    loop.start()


@gen.coroutine
def google_search_proxies():
    logger.debug('Searching google...')
    query = '+":8080" +":3128" +":80" filetype:txt -inurl:ftp'
    urls = yield get_google_results(query)
    print(*urls,sep='\n')
    raise gen.Return(urls)


@gen.coroutine
def call_subprocess(cmd, stdin_data=None, stdin_async=False):
    """
    Wrapper around subprocess call using Tornado's Subprocess class.
    """
    stdin = STREAM if stdin_async else subprocess.PIPE

    sub_process = process.Subprocess(
        cmd, stdin=stdin, stdout=STREAM, stderr=STREAM
    )

    if stdin_data:

        stdin_data = bytes(stdin_data, 'utf-8')
        if stdin_async:
            yield gen.Task(sub_process.stdin.write, stdin_data)
        else:
            print('yeah, here')
            sub_process.stdin.write(stdin_data)

    if stdin_async or stdin_data:
        sub_process.stdin.close()

    result, error = yield [
        gen.Task(sub_process.stdout.read_until_close),
        gen.Task(sub_process.stderr.read_until_close)
    ]

    raise gen.Return((result, error))


@gen.coroutine
def ping_proxy(proxy_string, timeout=3):
    '''
    Ping proxy server.
    '''
    proxy = proxy_from_string(proxy_string)
    parser = PingParser()
    ping_result = 'FAIL'
    ping_cmd = [
        'ping',
        '-q',
        '-w',
        '{}'.format(timeout),
        '-p',
        '{}'.format(proxy.port),
        '{}'.format(proxy.host)
    ]
    try:
        result, error = yield call_subprocess(ping_cmd, stdin_async=True)
        parsed_result = parser.parse(result.decode('utf-8'))
        if 'lost' in parsed_result:
            if parsed_result['lost'] == 0:
                ping_result = 'OK'
    except Exception as e:
        logger.debug(e)
    finally:
        raise gen.Return(ping_result)


def geoip_lookup(proxies):
    """
    Return geoip results for `proxies`.

    Uses ip-api.com.
    """
    wait = 0.5
    http_client = httpclient.HTTPClient()
    results = {}
    root_url = 'http://ip-api.com/json'
    for proxy in proxies:
        ip = proxy.split(':')[0]
        ip = ip.split(' ')[0]
        url = '{}/{}'.format(root_url, ip)
        logger.info(url)
        try:
            response = http_client.fetch(url, request_timeout=5)
            result = json.loads(response.body.decode('utf8'))
        except Exception as e:
            result = str(e)

        results[proxy] = result
        time.sleep(wait)

    http_client.close()
    return results



