#!/usr/bin/env python3
"""Standalone server for the apartment / Wi-Fi sensing editor (editor/sim.html).

    python3 editor/sim_editor.py                      # your layout in sim/apartment (local, gitignored), else the example
    python3 editor/sim_editor.py --dir examples/apartment --port 8010

Open http://localhost:8010/ . Layout files live in --dir:
  apartment.json   size and walls (written by sim/apartment/build_apartment.py from a floor plan, or by hand)
  furniture.json   boxes, round things, rugs, carpet, virtual doors (edited in the page)
  wifi.json        sockets, router, ESP32 nodes (edited in the page)
  floorplan.png    optional background image
Everything here is local: the server binds to 127.0.0.1 only and nothing is sent anywhere.
"""
import argparse
import datetime
import json
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
SIM_DIR = REPO / 'sim/apartment'
HISTORY_KEEP = 50
HISTORY_EVERY_S = 60
WIFI_FILE = 'wifi.json'
WIFI_KINDS = ('sockets', 'routers', 'nodes')


def read_wifi():
    try:
        raw = json.loads((SIM_DIR / WIFI_FILE).read_text())
    except (OSError, ValueError):
        raw = {}
    return {k: raw.get(k, []) for k in WIFI_KINDS}


def sim_data():
    apt = json.loads((SIM_DIR / 'apartment.json').read_text())
    furn = json.loads((SIM_DIR / 'furniture.json').read_text()) if (SIM_DIR / 'furniture.json').exists() else {}
    walls = [w for w in apt['walls'] if w['kind'] != 'furniture']
    return {'size': apt['size_m'], 'walls': walls, 'floorplan': apt.get('floorplan'),
            'furniture': {k: furn.get(k, []) for k in ('boxes', 'cylinders', 'rugs', 'carpet', 'barriers')},
            'wifi': read_wifi()}


def clean_furniture(furn):
    """The editor's layout, validated, with unique names."""
    def num(v, lo=-1.0, hi=20.0):
        v = float(v)
        if not lo <= v <= hi:
            raise ValueError(f'{v} out of range')
        return round(v, 3)
    clean = {'note': 'Furniture for the simulator, edited on the Sim page. Local only.'}
    for kind, fields in (('boxes', ('x0', 'y0', 'x1', 'y1', 'h')), ('cylinders', ('x', 'y', 'r', 'h')),
                         ('rugs', ('x0', 'y0', 'x1', 'y1')), ('carpet', ('x0', 'y0', 'x1', 'y1')),
                         ('barriers', ('x0', 'y0', 'x1', 'y1'))):
        out = []
        for i, item in enumerate(furn.get(kind, [])):
            row = {f: num(item[f]) for f in fields}
            if 'x1' in row and (row['x1'] <= row['x0'] or row['y1'] <= row['y0']):
                raise ValueError(f'{kind} {i}: zero or negative size')
            name = ''.join(c if c.isalnum() or c in '_-' else '_' for c in str(item.get('name', f'{kind}{i}')))[:40]
            rgb = [num(c, 0, 1) for c in item.get('rgb', [0.6, 0.6, 0.6])][:3]
            out.append({'name': name or f'{kind}{i}', **row, **({'rgb': rgb} if kind not in ('carpet', 'barriers') else {})})
        clean[kind] = out
    seen = set()                     # duplicate names get _2, _3 ... (the simulator needs unique names)
    for k in ('boxes', 'cylinders', 'rugs', 'barriers'):
        for o in clean[k]:
            base, n = o['name'], 2
            while o['name'] in seen:
                o['name'], n = f'{base}_{n}', n + 1
            seen.add(o['name'])
    return clean


def clean_wifi(wifi):
    """The Wi-Fi sensing layer, validated: wall sockets, the router (at most one) and ESP32 nodes."""
    clean = {'note': 'Wi-Fi sensing layout (sockets, router, ESP32 nodes), edited on the Sim page. Local only.'}
    seen = set()
    for kind in WIFI_KINDS:
        out = []
        for i, item in enumerate(wifi.get(kind, [])):
            x, y = float(item['x']), float(item['y'])
            if not (-1.0 <= x <= 20.0 and -1.0 <= y <= 20.0):
                raise ValueError(f'{kind} {i}: position out of range')
            base = ''.join(c if c.isalnum() or c in '_-' else '_' for c in str(item.get('name', f'{kind}{i}')))[:40] or f'{kind}{i}'
            name, n = base, 2
            while name in seen:
                name, n = f'{base}_{n}', n + 1
            seen.add(name)
            row = {'name': name, 'x': round(x, 3), 'y': round(y, 3)}
            if kind == 'nodes':
                row['mmwave'] = bool(item.get('mmwave'))
                row['tx'] = bool(item.get('tx'))
                if item.get('aim') is not None:
                    row['aim'] = round(float(item['aim']) % 360, 1)
            out.append(row)
        if kind == 'routers' and len(out) > 1:
            raise ValueError('only one router')
        clean[kind] = out
    return clean


def write_wifi(wifi):
    clean = clean_wifi(wifi)
    path = SIM_DIR / WIFI_FILE
    if not any(clean[k] for k in WIFI_KINDS) and not path.exists():
        return clean
    text = json.dumps(clean, indent=1)
    if not path.exists() or path.read_text() != text:
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(text)
        tmp.replace(path)                      # atomic: a crash mid-write never leaves half a file
    return clean


def rebuild():
    script = SIM_DIR / 'build_apartment.py'
    if script.exists():
        subprocess.run([sys.executable, str(script)], check=True, capture_output=True, timeout=60)


def write_furniture(furn, do_rebuild=False):
    """Write furniture.json and, at most once a minute, a timestamped copy in history/ (last HISTORY_KEEP kept)."""
    clean = clean_furniture(furn)
    text = json.dumps(clean, indent=1)
    path = SIM_DIR / 'furniture.json'
    if not path.exists() or path.read_text() != text:
        history = SIM_DIR / 'history'
        history.mkdir(exist_ok=True)
        copies = sorted(history.glob('furniture-*.json'))
        if not copies or time.time() - copies[-1].stat().st_mtime > HISTORY_EVERY_S:
            (history / f'furniture-{datetime.datetime.now():%Y%m%d-%H%M%S}.json').write_text(text)
            for old in sorted(history.glob('furniture-*.json'))[:-HISTORY_KEEP]:
                old.unlink()
        tmp = path.with_suffix('.json.tmp')
        tmp.write_text(text)
        tmp.replace(path)
    if do_rebuild:
        rebuild()
    return dict(sim_data(), saved_at=datetime.datetime.now().strftime('%H:%M:%S'))


def sim_versions():
    return sorted((p.stem[len('furniture-'):] for p in (SIM_DIR / 'history').glob('furniture-*.json')), reverse=True)


def restore_version(stamp):
    path = SIM_DIR / 'history' / f'furniture-{stamp}.json'
    if not stamp.replace('-', '').isdigit() or not path.exists():
        raise ValueError('no such version')
    return write_furniture(json.loads(path.read_text()))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, code, body, ctype='application/json'):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/sim'):
            return self.reply(200, (HERE / 'sim.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/sim/data':
            try:
                return self.reply(200, sim_data())
            except (OSError, ValueError) as error:
                return self.reply(404, {'error': f'no apartment in {SIM_DIR} ({error})'})
        if path == '/sim/versions':
            return self.reply(200, {'versions': sim_versions()})
        if path == '/sim/floorplan.png':
            try:
                return self.reply(200, (SIM_DIR / 'floorplan.png').read_bytes(), 'image/png')
            except OSError:
                return self.reply(404, {'error': 'no floor plan'})
        self.reply(404, {'error': 'not found'})

    def do_POST(self):
        if self.path not in ('/sim/furniture', '/sim/autosave', '/sim/restore', '/sim/wifi'):
            return self.reply(404, {'error': 'not found'})
        size = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(size) or b'{}')
            if self.path == '/sim/wifi':
                return self.reply(200, write_wifi(body))
            if self.path == '/sim/restore':
                return self.reply(200, restore_version(str(body.get('version', ''))))
            return self.reply(200, write_furniture(body, do_rebuild=self.path == '/sim/furniture'))
        except (ValueError, TypeError, KeyError) as error:
            return self.reply(400, {'error': str(error)})
        except (OSError, subprocess.SubprocessError) as error:
            return self.reply(500, {'error': f'failed: {error}'})


def main():
    global SIM_DIR
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dir', help='folder with apartment.json (default: sim/apartment if it has one, else examples/apartment)')
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()
    SIM_DIR = Path(args.dir).resolve() if args.dir else (SIM_DIR if (SIM_DIR / 'apartment.json').exists() else REPO / 'examples/apartment')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Sim editor on http://localhost:{args.port}/  (layout: {SIM_DIR})')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
