#!/usr/bin/env python3
"""Threshold-free paired summaries for E10.

The experimental unit for interval calculation is the configuration
(c, service-time law, offered load). Each configuration first averages
its three same-seed Delta-oracle pairs. A deterministic bootstrap over
these 54 configuration means reports descriptive 95% intervals.
"""
from pathlib import Path
import csv
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
rows = []
for line in (ROOT / 'results/e10_confirm.txt').read_text().splitlines():
    if not line.startswith('TAG '):
        continue
    parts = line.split()
    tag = parts[1].split(':')
    r = {'algo': tag[1], 'c': int(tag[2]), 'dist': tag[3],
         'rho': float(tag[4]), 'seed': int(tag[5])}
    for tok in parts[3:]:
        if '=' not in tok:
            continue
        k, v = tok.split('=', 1)
        try:
            r[k] = float(v)
        except ValueError:
            r[k] = v
    rows.append(r)

by = {(r['algo'], r['c'], r['dist'], r['rho'], r['seed']): r for r in rows}
pairs = []
for (algo, c, dist, rho, seed), d in sorted(by.items()):
    if algo != 'delta':
        continue
    o = by[('static', c, dist, rho, seed)]
    pairs.append({
        'c': c, 'dist': dist, 'rho': rho, 'seed': seed,
        'util_diff': d['util'] - o['util'],
        'rtt_ratio': d['meanLatOverS'] / o['meanLatOverS'],
    })

cells = {}
for r in pairs:
    key = (r['c'], r['dist'], r['rho'])
    cells.setdefault(key, []).append(r)
cell_rows = []
for (c, dist, rho), rs in sorted(cells.items()):
    cell_rows.append({
        'c': c, 'dist': dist, 'rho': rho,
        'util_diff_mean': float(np.mean([r['util_diff'] for r in rs])),
        'rtt_ratio_mean': float(np.mean([r['rtt_ratio'] for r in rs])),
    })

rng = np.random.default_rng(20260926)
def ci(values, b=20000):
    a = np.asarray(values, dtype=float)
    draws = np.empty(b)
    for i in range(b):
        draws[i] = rng.choice(a, size=len(a), replace=True).mean()
    return float(a.mean()), float(np.quantile(draws, .025)), float(np.quantile(draws, .975))

u = [r['util_diff_mean'] for r in cell_rows]
r = [r['rtt_ratio_mean'] for r in cell_rows]
u_mean, u_lo, u_hi = ci(u)
r_mean, r_lo, r_hi = ci(r)
summary = [
    ('configurations', len(cell_rows)),
    ('median_util_diff', float(np.median(u))),
    ('mean_util_diff', u_mean),
    ('mean_util_diff_ci95_low', u_lo),
    ('mean_util_diff_ci95_high', u_hi),
    ('median_rtt_ratio', float(np.median(r))),
    ('mean_rtt_ratio', r_mean),
    ('mean_rtt_ratio_ci95_low', r_lo),
    ('mean_rtt_ratio_ci95_high', r_hi),
]

with (ROOT / 'results/tables/e10_effects_by_config.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=cell_rows[0].keys())
    w.writeheader(); w.writerows(cell_rows)
with (ROOT / 'results/tables/e10_effects_summary.csv').open('w', newline='') as f:
    w = csv.writer(f); w.writerow(['metric','value']); w.writerows(summary)
for k,v in summary:
    print(f'{k}={v}')
