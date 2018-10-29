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
import time
import yarl
# Proxytools
from .page import Page

# Module vars
_logger = logging.getLogger(__name__)


class TaskTimeout(Exception):
    """ Task Timeout Exception """
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

    async def _async_get_pages(self, urls, concurrency=10, headless=True, timeout=10):
         """
         Asynchronously get pages from `urls` using chromium.

         :param urls: URLs to get
         :param concurrency: number of concurrent chromium tabs to utilise
         :param headless: use chrome in headless mode

         :type urls: list
         :type concurrency: int
         :type headless: bool

         :returns: list
         """
         browser = await pyppeteer.launch({'headless': headless})
         pages = []
         # Create incognito tab
         context = await browser.createIncognitoBrowserContext()
         for chunk in self._chunker(urls, concurrency):
             new_pages = await asyncio.gather(
                 *[self.get_page(url, context, timeout=timeout) for url in chunk if url],
                 return_exceptions=True)
             pages.extend(new_pages)
         await context.close()
         await browser.close()
         return pages

    async def _async_get_source_urls(self, num=10, headless=True):
        """
        Scrape proxy sources from Google.

        :param num: number of results to fetch [1-100]
        :param headless: use chrome in headless mode

        :type num: int
        :type headless: bool

        :returns: list
        """
        if num < 1 or num > 100:
            raise ValueError('source `num` must be between 1-100]')

        urls = []
        browser = await pyppeteer.launch({'headless': headless})
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

        await tab.close()
        await context.close()
        await browser.close()

        return urls

    async def _async_test_proxy(self,
                                proxy,
                                url,
                                headless=True,
                                timeout=10,
                                selector=None):
        """
        Test `proxy` by attempting to load `url'.

        :param proxy: The proxy to test
        :param url: the URL to test against
        :param selector: css selector used to verify page load
        :param headless: run chrome headless mode
        :param timeout: the async task timeout

        :type proxy: proxytools.Proxy
        :type url: yarl.URL
        :type selector: str
        :type headless: bool
        :type timeout: int

        :returns: dict
        """
        browser = await pyppeteer.launch(
            {
                'headless': headless,
                'args': [
                    '--proxy-server=http={}'.format(str(proxy)),
                    '--proxy-server=https={}'.format(str(proxy)),
                ]

            }
        )
        # Create incognito tab
        context = await browser.createIncognitoBrowserContext()
        try:
            page = await self.get_page(url, context, timeout=timeout, selector=selector)
            status = 'OK'
        except Exception as e:
            status = str(e)

        await context.close()
        await browser.close()

        return {'proxy': str(proxy), 'status': status}

    async def _async_test_proxies(self,
                                  proxies,
                                  url,
                                  headless=True,
                                  timeout=10,
                                  concurrency=1,
                                  exit_success_count=None,
                                  selector=None):
        """
        Test `proxies` by attempting to load `url' and awaiting `selector`.

        :param proxies: list of proxies
        :param url: the URL to test the proxies against
        :param headless: run chrome headless mode
        :param timeout: seconds to wait before quitting each test
        :param concurrency: number of concurrent chromium tabs to utilise
        :param selector: css selector used to verify page load
        :param exit_success_count: exit when number of working proxies is reached

        :type proxies: list of proxytools.Proxy
        :type url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type exit_success_count: int

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
                    timeout=timeout, selector=selector) for proxy in chunk],
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

        # Handle cloudlflare
        html = await resp.text()
        if self.detect_cloudflare(html):
            _logger.info('Cloudflare detected - awaiting navigation')
            await asyncio.sleep(12)
            resp = await tab.reload()

        _logger.info('Got {}'.format(str(url)))
        if selector:
            await tab.waitForSelector(selector, timeout=timeout*1000)
        html = await resp.text()
        # Close page tab
        await tab.close()
        page = Page(url=url, html=html)
        return page

    def get_pages(self, urls, timeout=10, headless=True):
        """
        Get pages from `urls` using chromium browser.

        Uses async functions to fetch the pages in concurrent browser
        tabs.

        :param urls: list of URL strings
        :type urls: list
        :returns: proxytools.page.Page
        """
        # Convert url strings in to yarl.URLs
        urls = [yarl.URL(url) for url in urls]
        results = self.loop.run_until_complete(self._async_get_pages(urls, timeout=timeout, headless=headless))
        pages = []
        for result in results:
            if isinstance(result, Page):
                pages.append(result)
            else:
                _logger.warning(result)

        return pages

    def get_source_urls(self, headless=True, num=10):
        """
        Search Google for URLs containing free proxy lists.

        :param num: number of proxy sources to get from Google
        :param headless: run chrome headless mode

        :type num: int
        :type headless: bool

        :returns: list
        """
        _logger.info('Searching Google for proxy sources..')
        return self.loop.run_until_complete(
            self._async_get_source_urls(headless=headless, num=num))

    def get_pages_with_proxies(self, source_num=10, headless=True):
        """
        Scrape the web for pages containing proxies.

        :param source_num: number of proxy sources to get from Google
        :param headless: run chrome headless mode

        :type source_num: int
        :type headless: bool

        :returns: list
        """
        urls = self.get_source_urls(num=source_num, headless=headless)
        _logger.info('Found {} source URLs'.format(len(urls)))
        pages = self.get_pages(urls)
        _logger.info('Downloaded {} pages'.format(len(pages)))
        proxy_pages = [page for page in pages if page.contains_ips()]
        _logger.info('Found {} pages containing proxies'.format(len(pages)))
        return proxy_pages

    def search_proxies(self, source_num=10, headless=True):
        """
        Scrape the web for proxies.

        :param source_num: number of proxy sources to get from Google
        :param headless: run chrome headless mode

        :type source_num: int
        :type headless: bool

        :returns: list
        """
        proxies = []
        proxy_pages = self.get_pages_with_proxies(source_num=source_num, headless=headless)
        for page in proxy_pages:
            proxies.extend(page.proxies())
        _logger.info('Scraped {} proxies'.format(len(proxies)))
        return proxies

    def test_proxies(self, proxies, url, timeout=10,
                     selector=None, headless=True, concurrency=2,
                     exit_success_count=None):
        """
        Test proxies can load page at `url`.

        :param proxies: list of proxies
        :param url: the URL to test the proxies against
        :param headless: run chrome headless mode
        :param timeout: seconds to wait before quitting each test
        :param concurrency: number of concurrent chromium tabs to utilise
        :param selector: css selector used to verify page load
        :param exit_success_count: exit when number of working proxies is reached

        :type proxies: list of proxytools.Proxy
        :type url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type exit_success_count: int

        :returns: dict
        """
        return self.loop.run_until_complete(
            self._async_test_proxies(proxies,
                                     url,
                                     timeout=timeout,
                                     concurrency=concurrency,
                                     selector=selector,
                                     exit_success_count=exit_success_count,
                                     headless=headless))

    def get_proxies(self, test_url, limit=10, timeout=10,
                    selector=None, headless=True, concurrency=2,
                    source_num=10):
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

        :type proxies: list of proxytools.Proxy
        :type test_url: yarl.URL
        :type headless: bool
        :type timeout: int
        :type concurrency: int
        :type selector: str
        :type source_num: int

        :returns: dict
        """
        proxies = self.search_proxies(source_num=source_num, headless=headless)

        results = self.test_proxies(proxies, test_url,
                                    headless=headless, concurrency=concurrency,
                                    selector=selector, exit_success_count=limit)
        print(proxies)
        proxies = [r for r in results if r['status'] == 'OK']
        return proxies[0:limit]

