import argparse
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from db import DB
from sql import SQLError

HERE = os.path.dirname(os.path.abspath(__file__))
L = threading.Lock()
D = None


class H(BaseHTTPRequestHandler):
    def send(s, code, body, ct='application/json'):
        b = body if isinstance(body, bytes) else json.dumps(body).encode()
        s.send_response(code)
        s.send_header('Content-Type', ct)
        s.send_header('Content-Length', str(len(b)))
        s.end_headers()
        s.wfile.write(b)

    def do_GET(s):
        if s.path == '/':
            with open(os.path.join(HERE, 'web', 'index.html'), 'rb') as f:
                s.send(200, f.read(), 'text/html; charset=utf-8')
        elif s.path == '/api/tables':
            with L:
                s.send(200, D.run('SHOW TABLES')[0])
        else:
            s.send(404, {'error': 'not found'})

    def do_POST(s):
        if s.path != '/api/query':
            return s.send(404, {'error': 'not found'})
        try:
            q = json.loads(s.rfile.read(int(s.headers.get('Content-Length', 0))))['sql']
            with L:
                s.send(200, {'results': D.run(q)})
        except SQLError as e:
            s.send(400, {'error': str(e)})
        except (ValueError, KeyError):
            s.send(400, {'error': 'send JSON like {"sql": "..."}'})

    def log_message(s, *a):
        pass


def main():
    global D
    a = argparse.ArgumentParser()
    a.add_argument('--db', default='data.json')
    a.add_argument('--port', type=int, default=8000)
    a = a.parse_args()
    D = DB(a.db)
    print(f'http://127.0.0.1:{a.port}  (db: {a.db})')
    try:
        ThreadingHTTPServer(('127.0.0.1', a.port), H).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        D.close()


if __name__ == '__main__':
    main()
