# -*- coding: utf-8 -*-
#!/usr/bin/env python
"""
Module containing ProxyTool class.
"""
import asyncio
import datetime
import itertools
import logging
import pyppeteer
import re
import requests
import socket
import time
import yarl
# Proxytools
from .page import Page
from .proxy import Proxy

# Module vars
_logger = logging.getLogger(__name__)


class TaskTimeout(Exception):
    """ Task Timeout Exception """
    pass

class TaskError(Exception):
    """ Generic Task Exception """
    pass

class ProxyToolError(Exception):
    """
    Generic Proxytools exception
    """
    pass


class Client:
    """
    Proxytools client.

    The is the main entry point for proxytools.
    """
    def __init__(self):
        self.loop = asyncio.get_event_loop()
        self.geoip_url = yarl.URL('http://ip-api.com/json/')
        self.whois_server = 'whois.apnic.net'

    def _chunker(self, iterable, n, fillvalue=None):
        """
        Split `iterable` into chunks of size `n`.

        :param iterable: iterator to chunk
        :param n: chunk size
        :param fillvalue: use value as padding

        :type iterable: list
        :type n: int
        :type fillvalue: str or int

        :returns: iterator
        """
        args = [iter(iterable)] * n
        return itertools.zip_longest(*args, fillvalue=fillvalue)

    def detect_cloudflare(self, html):
        """
        Return True if html is cloudflare.
        """
        pattern = '.*Checking your browser before accessing.*'
        if re.search(pattern, html):
            return True
        else:
            return False

    async def _async_get_pages(self, urls, concurrency=10, headless=True,
                               timeout=10, bin_path=None, chrome_args=[]):
        """
        Asynchronously get pages from `urls` using chromium.

        :param urls: URLs to get
        :param concurrency: number of concurrent chromium tabs to utilise
        :param headless: use chrome in headless mode
        :param bin_path: path to chrome executable
        :param chrome_args: headless chrome args

        :type urls: list
        :type concurrency: int
        :type headless: bool
        :type bin_path: str
        :type chrome_args: list

        :returns: list
        """
        kwargs = {
            'headless': headless,
            'args': chrome_args
        }
        if bin_path:
            kwargs['executablePath'] = bin_path
        browser = await pyppeteer.launch(kwargs)
        # browser = await pyppeteer.launch({'headless': headless})
        pages = []
        # Create incognito tab
        context = await browser.createIncognitoBrowserContext()
        for chunk in self._chunker(urls, concurrency):
            new_pages = await asyncio.gather(
                *[self.get_page(url, context, timeout=timeout) for url in chunk if url],
                return_exceptions=True)
            pages.extend(new_pages)

        # Cleanup
        try:
            await context.close()
        except:
            pass

        try:
            await browser.close()
        except:
            pass

        return pages

    async def _async_get_source_urls(self, num=10, headless=True, bin_path=None, chrome_args=[]):
        """
        Scrape proxy sources from Google.

        :param num: number of results to fetch [1-100]
        :param headless: use chrome in headless mode
        :param bin_path: path to chrome executable
        :param chrome_args: headless chrome args

        :type num: int
        :type headless: bool
        :type bin_path: str
        :type chrome_args: list

        :returns: list
        """
        if num < 1 or num > 100:
            raise ValueError('source `num` must be between 1-100]')

        urls = []
        kwargs = {
            'headless': headless,
            'args': chrome_args
        }
        if bin_path:
            kwargs['executablePath'] = bin_path
        browser = await pyppeteer.launch(kwargs)
        # browser = await pyppeteer.launch({'headless': headless})
        # Create incognito tab
        context = await browser.createIncognitoBrowserContext()
        tab = await context.newPage()
        await tab._client.send('Emulation.clearDeviceMetricsOverride');
        await tab.goto('https://www.google.com/search?q=free+proxy+list&gws_rd=cr&num={}'.format(num))
        results = await tab.querySelectorAll('div.srg div.r ')
        for result in results:
            link = await result.querySelector('a')
            prop = await link.getProperty('href')
            url =  await prop.jsonValue()
            urls.append(url)

        # Cleanup
        try:
            await tab.close()
        except:
            pass

        try:
            await context.close()
        except:
            pass

        try:
            await browser.close()
        except:
            pass

        return urls

    async def _async_test_proxy(self,
                                proxy,
                                url,
                                headless=True,
                                timeout=10,
                                bin_path=None,
                                chrome_args=[],
                                selector=None):
        """
        Test `proxy` by attempting to load `url'.

        :param proxy: The proxy to test
        :param url: the URL to test against
        :param selector: css selector used to verify page load
        :param headless: run chrome headless mode
        :param timeout: the async task timeout
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type proxy: proxytools.Proxy
        :type url: yarl.URL
        :type selector: str
        :type headless: bool
        :type timeout: int
        :type bin_path: str
        :type chrome_args: list

        :returns: dict
        """
        chrome_args.append('--proxy-server=http={}'.format(str(proxy)))
        chrome_args.append('--proxy-server=https={}'.format(str(proxy)))

        kwargs = {
            'headless': headless,
            'args':  chrome_args
        }

        if bin_path:
            kwargs['executablePath'] = bin_path

        browser = await pyppeteer.launch(kwargs)

        # Create incognito tab
        context = await browser.createIncognitoBrowserContext()
        try:
            page = await self.get_page(url, context, timeout=timeout, selector=selector)
            status = 'OK'
        except Exception as e:
            status = str(e)

        # Cleanup
        try:
            await context.close()
        except:
            pass

        try:
            await browser.close()
        except:
            pass

        return {'proxy': str(proxy), 'status': status}

    async def _async_test_proxies(self,
                                  proxies,
                                  url,
                                  headless=True,
                                  timeout=10,
                                  concurrency=1,
                                  exit_success_count=None,
                                  selector=None,
                                  bin_path=None,
                                  chrome_args=[]):
        """
        Test `proxies` by attempting to load `url' and awaiting `selector`.

        :param proxies: list of proxies
        :param url: the URL to test the proxies against
        :param headless: run chrome headless mode
        :param timeout: seconds to wait before quitting each test
        :param concurrency: number of concurrent chromium tabs to utilise
        :param selector: css selector used to verify page load
        :param exit_success_count: exit when number of working proxies is reached
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type proxies: list of proxytools.Proxy
        :type url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type exit_success_count: int
        :type bin_path: str
        :type chrome_args: list

        :returns: dict
        """
        results = []
        count = 0
        status_ok_count = 0
        start_ts = datetime.datetime.now()
        for chunk in self._chunker(proxies, concurrency):
            n_results = await asyncio.gather(
                *[self._async_test_proxy(
                    proxy, url, headless=headless,
                    timeout=timeout, selector=selector, bin_path=bin_path, chrome_args=chrome_args) for proxy in chunk],
                return_exceptions=True)
            count += len(chunk)
            minutes = round((datetime.datetime.now() - start_ts).seconds / 60, 2)
            _logger.info('Tested {} of {} proxies in {} minutes'
                         .format(count, len(proxies), minutes))
            for result in n_results:
                results.append(result)
                if isinstance(result, dict):
                    if result['status'] == 'OK':
                        status_ok_count += 1
                    if exit_success_count is not None:
                        if status_ok_count == exit_success_count:
                            return results
            # results.extend(n_results)
        return results

    async def get_page(self, url, context, timeout=10, selector=None):
        """
        Asynchronously fetch page from `url` using chromium
        browser `context`.

        :param url: the page URL
        :param context: pyppeteer browser context
        :param timeout: seconds to wait before quiting
        :param selector: css selector used to verify page load

        :type url: yarl.URL
        :type context: pyppeteer.browser.BrowserContext
        :type timeout: int
        :type selector: str

        :returns: Page
        :raises: TaskTimeout
        """
        tab = await context.newPage()
        # Fix viewport
        await tab._client.send('Emulation.clearDeviceMetricsOverride');
        _logger.info('Fetching {}'.format(url))
        # Get page html
        # Proxy timeouts don't seem to respect load_timeout, so enforce it with asyncio
        try:
            resp = await asyncio.wait_for(tab.goto(str(url), timeout=timeout*1000), timeout=timeout)
        except asyncio.TimeoutError:
            _logger.warning('Timed out fetching: {}'.format(str(url)))
            raise TaskTimeout('Navigation timed out')
        except Exception as e:
            raise TaskError(str(e))

        # Handle cloudlflare
        html = await resp.text()
        if self.detect_cloudflare(html):
            _logger.info('Cloudflare detected - awaiting navigation')
            await asyncio.sleep(12)
            try:
                resp = await asyncio.wait_for(tab.reload(), timeout=timeout)
            except asyncio.TimeoutError:
                _logger.warning('Timed out fetching: {}'.format(str(url)))
                raise TaskTimeout('Navigation timed out')
            except Exception as e:
                raise TaskError(str(e))

        _logger.info('Got {}'.format(str(url)))
        if selector:
            await tab.waitForSelector(selector, timeout=timeout*1000)
        html = await resp.text()
        # Close page tab
        try:
            await tab.close()
        except:
            pass
        page = Page(url=url, html=html)
        return page

    def get_pages(self, urls, timeout=10, headless=True, bin_path=None, chrome_args=[]):
        """
        Get pages from `urls` using chromium browser.

        Uses async functions to fetch the pages in concurrent browser
        tabs.

        :param urls: list of URL strings
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type urls: list
        :type bin_path: str
        :type chrome_args: list

        :type urls: list
        :type bin_path: str

        :returns: proxytools.page.Page
        """
        # Convert url strings in to yarl.URLs
        urls = [yarl.URL(url) for url in urls]
        results = self.loop.run_until_complete(
            self._async_get_pages(urls,
                                  timeout=timeout,
                                  headless=headless,
                                  bin_path=bin_path,
                                  chrome_args=chrome_args))
        pages = []
        for result in results:
            if isinstance(result, Page):
                pages.append(result)
            else:
                _logger.warning(result)

        return pages

    def get_source_urls(self, headless=True, num=10, bin_path=None, chrome_args=[]):
        """
        Search Google for URLs containing free proxy lists.

        :param num: number of proxy sources to get from Google
        :param headless: run chrome headless mode
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type num: int
        :type headless: bool
        :type bin_path: str
        :type chrome_args: list

        :returns: list
        """
        _logger.info('Searching Google for proxy sources..')
        return self.loop.run_until_complete(
            self._async_get_source_urls(headless=headless, num=num, bin_path=bin_path, chrome_args=chrome_args))

    def get_pages_with_proxies(self, source_num=10, headless=True, bin_path=None, chrome_args=[]):
        """
        Scrape the web for pages containing proxies.

        :param source_num: number of proxy sources to get from Google
        :param headless: run chrome headless mode
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type source_num: int
        :type headless: bool
        :type bin_path: str
        :type chrome_args: list

        :returns: list
        """
        urls = self.get_source_urls(num=source_num, headless=headless, bin_path=bin_path, chrome_args=chrome_args)
        _logger.info('Found {} source URLs'.format(len(urls)))
        pages = self.get_pages(urls, headless=headless, bin_path=bin_path, chrome_args=chrome_args)
        _logger.info('Downloaded {} pages'.format(len(pages)))
        proxy_pages = [page for page in pages if page.contains_ips()]
        _logger.info('Found {} pages containing proxies'.format(len(pages)))
        return proxy_pages

    def search_proxies(self, source_num=10, headless=True, bin_path=None, chrome_args=[]):
        """
        Scrape the web for proxies.

        :param source_num: number of proxy sources to get from Google
        :param headless: run chrome headless mode
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type source_num: int
        :type headless: bool
        :type bin_path: str
        :type chrome_args: list

        :returns: list
        """
        proxies = []
        proxy_pages = self.get_pages_with_proxies(source_num=source_num,
                                                  headless=headless,
                                                  bin_path=bin_path,
                                                  chrome_args=chrome_args)
        for page in proxy_pages:
            proxies.extend(page.proxies())
        _logger.info('Scraped {} proxies'.format(len(proxies)))
        return proxies

    def test_proxies(self, proxies, url, timeout=10,
                     selector=None, headless=True, concurrency=2,
                     exit_success_count=None, bin_path=None, chrome_args=[]):
        """
        Test proxies can load page at `url`.

        :param proxies: list of proxies
        :param url: the URL to test the proxies against
        :param headless: run chrome headless mode
        :param timeout: seconds to wait before quitting each test
        :param concurrency: number of concurrent chromium tabs to utilise
        :param selector: css selector used to verify page load
        :param exit_success_count: exit when number of working proxies is reached
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type proxies: list of proxytools.Proxy
        :type url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type exit_success_count: int
        :type bin_path: str
        :type chrome_args: list

        :returns: dict
        """
        return self.loop.run_until_complete(
            self._async_test_proxies(proxies,
                                     url,
                                     timeout=timeout,
                                     concurrency=concurrency,
                                     selector=selector,
                                     exit_success_count=exit_success_count,
                                     headless=headless,
                                     bin_path=bin_path,
                                     chrome_args=chrome_args))

    def get_proxies(self, test_url, limit=10, timeout=10,
                    selector=None, headless=True, concurrency=2,
                    source_num=10, bin_path=None, chrome_args=[]):
        """
        Scrape the web for working proxies.
        Test proxies can load `test_url`.

        :param proxies: list of proxies
        :param test_url: the URL to test the proxies against
        :param headless: run chrome headless mode
        :param timeout: seconds to wait before quitting each test
        :param concurrency: number of concurrent chromium tabs to utilise
        :param selector: css selector used to verify proxy is working
        :param source_num: number of proxy sources to get from Google
        :param bin_path: path to chrome executable
        :param chrome_args: headless chromium args

        :type proxies: list of proxytools.Proxy
        :type test_url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type source_num: int
        :type bin_path: str
        :type chrome_args: list

        :returns: dict
        """
        proxies = self.search_proxies(source_num=source_num,
                                      headless=headless,
                                      bin_path=bin_path,
                                      chrome_args=chrome_args)

        results = self.test_proxies(proxies,
                                    test_url,
                                    headless=headless,
                                    concurrency=concurrency,
                                    selector=selector,
                                    exit_success_count=limit,
                                    bin_path=bin_path,
                                    chrome_args=chrome_args)
        proxies = [r for r in results if r['status'] == 'OK']
        return proxies[0:limit]

    def get_geography(self, proxies):
        """
        Get geographic location of `proxies`.

        :param proxies: list of proxy URLs
        :type proxies: list
        :returns: dict
        """
        results = {}
        for p in proxies:
            proxy = Proxy.from_string(p)
            country = proxy.country()
            results[p] = country
            time.sleep(1)

        return results
