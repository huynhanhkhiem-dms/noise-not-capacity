#!/usr/bin/env python3
"""Summarize the E10 finite-horizon robustness block.

A run is good under the manuscript criterion when Delta utilization is at least
95% of the static oracle in the same (c, law, rho, seed) cell and mean RTT is
at most 1.5 mean service times.
"""
from pathlib import Path
import csv
import sys

root = Path(__file__).resolve().parents[1]
rows = []
input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else (root / 'results/e10_confirm.txt')
for line in input_path.read_text().splitlines():
    if not line.startswith('TAG '):
        continue
    parts = line.split()
    tag = parts[1].split(':')
    row = {'algo': tag[1], 'c': int(tag[2]), 'dist': tag[3], 'rho': float(tag[4]), 'seed': int(tag[5])}
    for tok in parts[3:]:
        if '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        try: row[k] = float(v)
        except ValueError: row[k] = v
    rows.append(row)

by = {(r['algo'], r['c'], r['dist'], r['rho'], r['seed']): r for r in rows}
out = []
for k, d in sorted((k, v) for k, v in by.items() if k[0] == 'delta'):
    _, c, dist, rho, seed = k
    o = by[('static', c, dist, rho, seed)]
    good = d['util'] >= 0.95 * o['util'] and d['meanLatOverS'] <= 1.5
    out.append({
        'c': c, 'dist': dist, 'rho': rho, 'seed': seed,
        'delta_util': d['util'], 'oracle_util': o['util'],
        'delta_meanLatOverS': d['meanLatOverS'], 'delta_limitOverC': d['limitOverC'],
        'good': int(good),
    })

p = root / 'results/e10_confirm_summary.csv'
with p.open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=out[0].keys())
    w.writeheader(); w.writerows(out)

print(f'E10 Delta good: {sum(r["good"] for r in out)}/{len(out)}')
for dist in sorted({r['dist'] for r in out}):
    s = [r for r in out if r['dist'] == dist]
    print(f'  {dist}: {sum(r["good"] for r in s)}/{len(s)}')
