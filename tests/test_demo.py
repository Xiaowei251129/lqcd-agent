"""The local demo must not accept cross-origin requests or arbitrary actions."""
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
from lqcd_agent.demo.server import Handler


def test_demo_limits_actions_and_browser_origin():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        for method, path, headers, status in [
            ('GET', '/', {}, 200), ('POST', '/arbitrary-command', {}, 404),
            ('POST', '/run', {'Origin': 'https://untrusted.example'}, 403)]:
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request(method, path, headers=headers)
                response = connection.getresponse()
                assert response.status == status
                response.read()
            finally:
                connection.close()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)
        assert not worker.is_alive()
