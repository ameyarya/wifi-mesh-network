"""Tests for the editor server: python3 -m unittest discover -s editor"""
import json
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import sim_editor

EXAMPLE = Path(__file__).resolve().parent.parent / 'examples/apartment'


class EditorServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        for f in EXAMPLE.glob('*.json'):
            shutil.copy(f, cls.tmp / f.name)
        sim_editor.SIM_DIR = cls.tmp
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), sim_editor.Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        shutil.rmtree(cls.tmp)

    def get(self, path):
        with urllib.request.urlopen(self.url + path) as r:
            return json.loads(r.read())

    def post(self, path, body):
        req = urllib.request.Request(self.url + path, json.dumps(body).encode(), method='POST')
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_data_has_layout_and_wifi(self):
        d = self.get('/sim/data')
        self.assertEqual(d['size'], [6.0, 4.0])
        self.assertEqual(len(d['wifi']['nodes']), 3)

    def test_wifi_roundtrip_keeps_aim_and_makes_names_unique(self):
        status, w = self.post('/sim/wifi', {'nodes': [
            {'name': 'a', 'x': 1, 'y': 2, 'mmwave': True, 'aim': 370},
            {'name': 'a', 'x': 3, 'y': 2, 'tx': True}], 'sockets': [{'name': 's', 'x': 0, 'y': 0}]})
        self.assertEqual(status, 200)
        self.assertEqual([n['name'] for n in w['nodes']], ['a', 'a_2'])
        self.assertEqual(w['nodes'][0]['aim'], 10.0)                  # wraps into 0-360
        self.assertEqual(self.get('/sim/data')['wifi']['nodes'][1]['tx'], True)   # saved to disk

    def test_wifi_rejects_bad_input(self):
        self.assertEqual(self.post('/sim/wifi', {'nodes': [{'name': 'a', 'x': 99, 'y': 0}]})[0], 400)
        self.assertEqual(self.post('/sim/wifi', {'routers': [{'x': 1, 'y': 1}, {'x': 2, 'y': 2}]})[0], 400)
        self.assertEqual(self.post('/sim/wifi', {'nodes': [{'name': 'a'}]})[0], 400)

    def test_furniture_saves_with_history(self):
        d = self.get('/sim/data')
        status, out = self.post('/sim/autosave', d['furniture'])
        self.assertEqual(status, 200)
        self.assertEqual(self.post('/sim/autosave', {'boxes': [{'name': 'b', 'x0': 1, 'y0': 1, 'x1': 1, 'y1': 2, 'h': 1}]})[0], 400)  # zero width


if __name__ == '__main__':
    unittest.main()
