#!/usr/bin/env python3
"""Fetch the real inputs used to measure service-time distributions of four real request handlers.

  - PyPI project descriptions (READMEs) of the 1,500 most-downloaded projects
    (list: hugovk/top-pypi-packages, snapshot of 2026-09-01, data/raw/top-pypi-packages.min.json)
  - npm package documents ("packuments") of the 1,000 top packages of wooorm/npm-high-impact
  - Chinook sample database (lerocha/chinook-database, data/raw/Chinook_Sqlite.sqlite)
Outputs go to data/raw/. Every file is hashed in data/raw/MANIFEST.sha256 by the caller.
"""
import json, os, sys, time, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')

def get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except Exception as e:
            if k == tries - 1:
                return None
            time.sleep(1 + k)

def pypi():
    top = json.load(open(os.path.join(RAW, 'top-pypi-packages.min.json')))['rows'][:1500]
    names = [r['project'] for r in top]
    def one(n):
        b = get(f'https://pypi.org/pypi/{urllib.parse.quote(n)}/json')
        if not b: return None
        info = json.loads(b).get('info', {})
        return {'name': n, 'content_type': info.get('description_content_type'), 'description': info.get('description') or ''}
    with ThreadPoolExecutor(8) as ex:
        rows = [r for r in ex.map(one, names) if r]
    with open(os.path.join(RAW, 'pypi_descriptions.jsonl'), 'w') as f:
        for r in rows: f.write(json.dumps(r) + '\n')
    print('pypi descriptions:', len(rows))

def npm():
    # 1,000 most "high-impact" npm packages (wooorm/npm-high-impact, lib/top.js, data/raw/npm-high-impact-top.js)
    import re
    src = open(os.path.join(RAW, 'npm-high-impact-top.js')).read()
    names = list(dict.fromkeys(re.findall(r"'([^']+)'", src)))[:1000]
    os.makedirs(os.path.join(RAW, 'npm'), exist_ok=True)
    def one(n):
        b = get('https://registry.npmjs.org/' + n.replace('/', '%2F'))
        if not b: return 0
        with open(os.path.join(RAW, 'npm', n.replace('/', '__') + '.json'), 'wb') as f: f.write(b)
        return len(b)
    with ThreadPoolExecutor(8) as ex:
        sizes = [s for s in ex.map(one, names) if s]
    print('npm packuments:', len(sizes), 'total MB', round(sum(sizes) / 1e6, 1))

if __name__ == '__main__':
    what = sys.argv[1:] or ['pypi', 'npm']
    if 'pypi' in what: pypi()
    if 'npm' in what: npm()
