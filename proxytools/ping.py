import time
from datetime import timedelta
import click
import subprocess
from tornado import gen, ioloop, queues, process
from parser import PingParser

PING_TIMEOUT = 1
CONCURRENCY = 100
STREAM = process.Subprocess.STREAM

class PingError(Exception):
    """
    Represents a human-facing exception.
    """
    def __init__(self, message):
        self.message = message

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
def ping_proxies(proxies,
                 output_file=None,
                 timeout=PING_TIMEOUT,
                 concurrency=CONCURRENCY,
                 progress_bar=None):

    parser = PingParser()
    q = queues.Queue()
    start = time.time()
    fetching, fetched = set(), set()
    working_proxies = set()

    @gen.coroutine
    def ping_proxy():
        current_proxy = yield q.get()
        try:
            if current_proxy in fetching:
                return

            proxy_parts = current_proxy.split(':')
            proxy_host = proxy_parts[0]

            if len(proxy_parts) == 2:
                proxy_port = proxy_parts[1]
            else:
                proxy_port = 80

            #print('checking %s:%s' % (proxy_host, proxy_port))
            fetching.add(current_proxy)
            ping_cmd = [
                'ping',
                '-q',
                '-w',
                '{}'.format(timeout),
                '-p',
                '{}'.format(proxy_port),
                '{}'.format(proxy_host)
            ]
            try:
                result, error = yield call_subprocess(ping_cmd, stdin_async=True)
                parsed_result = parser.parse(result.decode('utf-8'))
                if 'lost' in parsed_result:
                    if parsed_result['lost'] == 0:
                        #print('OK')
                        working_proxies.add(current_proxy)
            except Exception as e:
                raise PingError(e)

            fetched.add(current_proxy)
            #print(len(fetched))
            if progress_bar:
                progress_bar.update(1)

        finally:
            q.task_done()

    @gen.coroutine
    def worker():
        while True:
            yield ping_proxy()

    for proxy in proxies:
        q.put(proxy)

    # Start workers, then wait for the work queue to be empty.
    for _ in range(concurrency):
        worker()
    yield q.join(timeout=timedelta(seconds=3600))
    assert fetching == fetched
    print('Done in %d seconds, tested %s proxies. Discarded %s proxies.' % (
        time.time() - start, len(fetched), len(proxies) - len(working_proxies)))

    if output_file is not None:
        with open(output_file, 'w+') as f:
            f.write('\n'.join(working_proxies))
