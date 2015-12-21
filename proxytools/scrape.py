import aiohttp
import asyncio
import pdb

@asyncio.coroutine
def get(*args, **kwargs):
    response = yield from aiohttp.request('GET', *args, **kwargs)
    pdb.set_trace()
    return (yield from response.read_and_close(decode=True))

def get_hrefs(page):
    soup = bs4.BeautifulSoup(page)
    a = soup.findAll('a')
    hrefs = [link['href'] for link in links]
    return hrefs

@asyncio.coroutine
def print_hrefs(query):
    url = 'http://putlocker.is/search/search.php?q={}'.format(query)
    page = yield from get(url, compress=True)
    print(page)
    hrefs = get_hrefs(page)
    print('{}: {}'.format(query, hrefs))

movies = ['spectre', 'star wars', 'sicario']
loop = asyncio.get_event_loop()
f = asyncio.wait([print_hrefs(m) for m in movies])
loop.run_until_complete(f)
