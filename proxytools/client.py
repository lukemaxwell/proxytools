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
import time
import yarl

from proxytools import Page

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
    def __init__(self):
        self.loop = asyncio.get_event_loop()

    def _chunker(self, iterable, n, fillvalue=None):
        args = [iter(iterable)] * n
        return itertools.zip_longest(*args, fillvalue=fillvalue)

    async def _async_get_pages(self, urls, concurrency=10, headless=True):
        browser = await pyppeteer.launch({'headless': headless})
        pages = []
        # Create incognito tab
        context = await browser.createIncognitoBrowserContext()
        for chunk in self._chunker(urls, concurrency):
            new_pages = await asyncio.gather(*[self.get_page(url, context) for url in chunk],
                                             return_exceptions=True)
            pages.extend(new_pages)
        await context.close()
        await browser.close()
        return pages

    async def _async_get_source_urls(self, num=10, headless=True):
        """
        Get proxy sources from Google.
        """
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
                                  selector=None):
        """
        Test `proxies` by attempting to load `url' and awaiting `selector`.

        :param proxies: list of proxies
        :param url: the URL to test the proxies against
        :param selector: css selector used to verify page load

        :type proxies: list of proxytools.Proxy
        :type url: yarl.URL
        :type context: pyppeteer.browser.BrowserContext
        :type selector: str

        :returns: dict
        """
        results = []
        count = 0
        start_ts = datetime.datetime.now()
        for chunk in self._chunker(proxies, concurrency):
            result = await asyncio.gather(*[self._async_test_proxy(proxy,
                                                                   url,
                                                                   headless=headless,
                                                                   timeout=timeout,
                                                                   selector=selector) for proxy in chunk],
                                          return_exceptions=True)
            count += len(chunk)
            minutes = (datetime.now() - start_ts).seconds / 60
            _logger.info('Tested {} of {} proxies in {} minutes'.format(count, len(proxies), minutes))
            results.extend(result)
        return results

    async def get_page(self, url, context, timeout=10, selector=None):
        """
        Asynchronously fetch page from `url` using chromium
        browser `context`.

        :param url: the page URL
        :param context: pyppeteer browser context

        :type url: yarl.URL
        :type context: pyppeteer.browser.BrowserContext

        :returns: Page
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
            raise TaskTimeout('Navigation timed out')
        _logger.info('Got {}'.format(str(url)))
        if selector:
            await tab.waitForSelector(selector, timeout=timeout*1000)
        html = await resp.text()
        # Close page tab
        await tab.close()
        page = Page(url=url, html=html)
        return page

    def get_pages(self, urls):
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
        results = self.loop.run_until_complete(self._async_get_pages(urls))
        pages = []
        for result in results:
            if isinstance(result, Page):
                pages.append(result)
            else:
                _logger.warning(result)

        return pages

    def get_source_urls(self):
        """
        Search Google for free proxy lists.
        """
        _logger.info('Searching Google for proxy sources..')
        return self.loop.run_until_complete(self._async_get_source_urls())

    def get_pages_with_proxies(self):
        """
        Scrape the web for pages containing proxies.
        """
        urls = self.get_source_urls()
        _logger.info('Found {} source URLs'.format(len(urls)))
        pages = self.get_pages(urls)
        _logger.info('Downloaded {} pages'.format(len(pages)))
        proxy_pages = [page for page in pages if page.contains_ips()]
        _logger.info('Found {} pages containing proxies'.format(len(pages)))
        return proxy_pages

    def get_proxies(self):
        """
        Scrape the web for proxies.
        """
        proxies = []
        proxy_pages = self.get_pages_with_proxies()
        for page in proxy_pages:
            proxies.extend(page.proxies())
        _logger.info('Scraped {} proxies'.format(len(proxies)))
        return proxies


    def test_proxies(self, proxies, url, timeout=10,
                     selector=None, headless=True, concurrency=1):
        """
        Test proxies can load page at 'url'.
        """
        return self.loop.run_until_complete(
            self._async_test_proxies(proxies,
                                     url,
                                     timeout=timeout,
                                     concurrency=concurrency,
                                     selector=selector,
                                     headless=headless))
