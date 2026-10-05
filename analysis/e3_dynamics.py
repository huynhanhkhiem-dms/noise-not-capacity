"""E3: dynamics under capacity, service-speed and load changes (c = 64, s = 10 ms, exp; 1800 s, changes at 600 s and 1200 s).
Per-second series come from results/ts/e3_<ctl>_<scenario>_<seed>.csv."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import LABEL

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'results', 'tables')
CTLS = ['vegas', 'vegasW', 'g2', 'g2W', 'envoy', 'failsafe', 'delta', 'static', 'deltaAny']
RHO = {'cap': [2.0, 4.0, 2.0], 'slow': [2.0, 4.0, 2.0], 'load': [0.5, 2.0, 0.5]}   # offered load relative to current capacity
S_MS = 10.0

def series(ctl, sc, seed):
    d = pd.read_csv(os.path.join(ROOT, 'results', 'ts', f'e3_{ctl}_{sc}_{seed}.csv'))
    d['util'] = d.completions * (S_MS / 1000.0) * d.s_scale / d.c
    d['lat'] = d.mean_rtt_ms / (S_MS * d.s_scale)
    d['rej'] = d.rejections / d.arrivals.clip(lower=1)
    d['limc'] = d['limit'] / d.c
    return d

def settle(d, t0, rho, win=10, hold=30):
    """Seconds after t0 until the win-s moving averages have util >= 0.9*min(1,rho) and latency <= 1.5 s
    and keep them for `hold` consecutive seconds (inf if never within the 600-s phase)."""
    seg = d[(d.t_s > t0) & (d.t_s <= t0 + 600)].reset_index(drop=True)
    u = seg.util.rolling(win, min_periods=win).mean(); l = seg.lat.rolling(win, min_periods=win).mean()
    ok = ((u >= 0.9 * min(1.0, rho)) & (l <= 1.5)).values
    run = 0
    for i, v in enumerate(ok):
        run = run + 1 if v else 0
        if run >= hold:
            return float(i - hold + 2 - win + 1) if i - hold + 2 - win + 1 > 0 else 0.0
    return np.inf

rows = []
for sc in ['cap', 'slow', 'load']:
    for ctl in CTLS:
        for seed in [1, 2, 3]:
            d = series(ctl, sc, seed)
            r = {'scenario': sc, 'ctl': ctl, 'seed': seed}
            for k, (a, b) in enumerate([(300, 600), (900, 1200), (1500, 1800)]):
                w = d[(d.t_s > a) & (d.t_s <= b)]
                rho = RHO[sc][k]
                r[f'util{k}'] = w.util.mean(); r[f'lat{k}'] = (w.mean_rtt_ms * w.completions).sum() / w.completions.sum() / (S_MS * w.s_scale.iloc[0])
                r[f'limc{k}'] = w.limc.mean(); r[f'xrej{k}'] = w.rejections.sum() / w.arrivals.sum() - max(0.0, 1 - 1 / rho)
            for k, t0 in enumerate([600, 1200]):
                r[f'settle{k+1}'] = settle(d, t0, RHO[sc][k + 1])
                w = d[(d.t_s > t0) & (d.t_s <= t0 + 30)]
                r[f'tlat{k+1}'] = w.lat.max(); r[f'tutil{k+1}'] = w.util.mean()
            rows.append(r)
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, 'e3_runs.csv'), index=False)
agg = df.drop(columns='seed').groupby(['scenario', 'ctl'], sort=False).agg(
    lambda x: np.inf if np.isinf(x).any() else x.mean()).reset_index()
agg.to_csv(os.path.join(OUT, 'e3_summary.csv'), index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
for sc in ['cap', 'slow', 'load']:
    t = agg[agg.scenario == sc].set_index('ctl')
    print(f'\n== {sc}: phases A/B/C = [300,600],[900,1200],[1500,1800]; settle = s after change (inf = never within 600 s)')
    print(t[['util0', 'lat0', 'util1', 'lat1', 'limc1', 'util2', 'lat2', 'xrej0', 'xrej2', 'settle1', 'settle2', 'tlat1', 'tlat2']].round(3).to_string())


# ---------------- slow load ramp 0.5 -> 1.5 -> 0.5 (30-s steps) ----------------
def rho_at(t):
    k = int((t - 1) // 30); tt = 30 * k
    if k == 0: return 0.5
    return 0.5 + tt / 900.0 if tt <= 900 else 1.5 - (tt - 900) / 900.0

rows = []
for ctl in CTLS:
    for seed in [1, 2, 3]:
        f = os.path.join(ROOT, 'results', 'ts', f'e3_{ctl}_ramp_{seed}.csv')
        if not os.path.exists(f): continue
        d = series(ctl, 'ramp', seed); d = d[d.t_s > 60].copy()
        d['rho'] = d.t_s.apply(rho_at)
        d['urel'] = d.util / d.rho.clip(upper=1.0)
        d['xrej'] = d.rej - (1 - 1 / d.rho).clip(lower=0)
        band = d[(d.rho >= 0.9) & (d.rho <= 1.1)]
        lat = (d.mean_rtt_ms * d.completions).sum() / d.completions.sum() / S_MS
        latb = (band.mean_rtt_ms * band.completions).sum() / band.completions.sum() / S_MS
        rows.append({'ctl': ctl, 'seed': seed, 'urel': d.urel.mean(), 'lat': lat, 'xrej': d.xrej.mean(),
                     'urel_band': band.urel.mean(), 'lat_band': latb, 'xrej_band': band.xrej.mean(),
                     'peak10': d.lat.rolling(10).mean().max(), 'limc_max': d.limc.max()})
if rows:
    r = pd.DataFrame(rows)
    r.to_csv(os.path.join(OUT, 'e3_ramp_runs.csv'), index=False)
    agg = r.drop(columns='seed').groupby('ctl', sort=False).mean()
    agg.to_csv(os.path.join(OUT, 'e3_ramp.csv'))
    print('\n== ramp 0.5 -> 1.5 -> 0.5 (t > 60 s); band = 0.9 <= rho <= 1.1\n', agg.round(3).to_string())
