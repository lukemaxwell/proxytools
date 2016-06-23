# -*- coding: utf-8 -*-
import time
from datetime import timedelta
from tornado import tcpclient, gen, ioloop, queues, process, netutil

TCP_TIMEOUT = 2
CONCURRENCY = 100

netutil.Resolver.configure('tornado.netutil.ThreadedResolver')

@gen.coroutine
def tcp_connections(proxies,
                     output_file,
                     progress_bar=None,
                     concurrency=CONCURRENCY,
                     timeout=TCP_TIMEOUT):

    @gen.coroutine
    def tcp_connection():
        current_proxy = yield q.get()
        if current_proxy in fetching:
            return

        proxy_parts = current_proxy.split(':')
        proxy_host = proxy_parts[0]

        if len(proxy_parts) == 2:
            proxy_port = int(proxy_parts[1])
        else:
            proxy_port = 80

        fetching.add(current_proxy)
        timeout = 1
        try:
            connect = yield gen.with_timeout(timedelta(seconds=timeout), client.connect(host=proxy_host, port=proxy_port))
            working_proxies.add(current_proxy)
        except:
            pass

        fetched.add(current_proxy)

        if progress_bar:
            progress_bar.update(1)

        q.task_done()

    @gen.coroutine
    def worker():
        while True:
            yield tcp_connection()

    q = queues.Queue()
    #client = tcpclient.TCPClient()
    netutil.Resolver.configure('tornado.netutil.ThreadedResolver')
    resolver = netutil.Resolver(io_loop=ioloop.IOLoop.current())
    client = tcpclient.TCPClient(resolver=resolver)
    start = time.time()
    fetching, fetched = set(), set()
    working_proxies = set()

    # Populate the queue
    for proxy in proxies:
        q.put(proxy)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(CONCURRENCY):
        worker()

    yield q.join(timeout=timedelta(seconds=300))
    assert fetching == fetched
    client.close()

    print('Done in %d seconds, fetched %s proxies. Found %s working proxies, discarded %s proxies.' % (
        time.time() - start, len(fetched), len(working_proxies), len(proxies) - len(working_proxies)))

    if output_file is not None:
        with open(output_file, 'w+') as f:
            f.write('\n'.join(working_proxies))
