"""E2: time-scale sweep (s = 1 ms .. 5 s, c = 64, rho = 2). Table 6 and the Envoy duty-cycle prediction."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'theory'))
from load import load, LABEL
import theory as T

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
df = load('e2.txt'); assert not df['error'].any()
order = ['delta', 'envoy', 'envoyScaled', 'failsafe', 'vegasW', 'g2W', 'static']
g = df.groupby(['ctl', 'S', 'dist'])[['util', 'meanLatOverS', 'limitOverC', 'p99OverS', 'eSd']].mean().reset_index()
g.to_csv(os.path.join(OUT, 'e2_cells.csv'), index=False)
pd.set_option('display.width', 250)
for m in ['util', 'meanLatOverS', 'limitOverC']:
    t = g.groupby(['ctl', 'S'])[m].mean().unstack('ctl')[order]   # mean over exp and ln1
    print(f'\n{m} (mean of exp and ln1, 3 seeds each)\n', t.round(3).to_string())
    t.to_csv(os.path.join(OUT, f'e2_{m}.csv'))
# Envoy with a scaled update window: measured utilisation loss vs predicted duty-cycle loss (Prop. 5(i))
rows = []
for S in sorted(df.S.unique()):
    p = T.envoy_probe_loss(S, 64)
    for dist in ['exp', 'ln1']:
        u = g[(g.ctl == 'envoyScaled') & (g.S == S) & (g.dist == dist)]['util'].iloc[0]
        us = g[(g.ctl == 'static') & (g.S == S) & (g.dist == dist)]['util'].iloc[0]
        rows.append({'S_ms': S, 'dist': dist, 'duty_pred': round(p['duty'], 4), 'loss_pred': round(p['loss'], 4),
                     'loss_meas_vs_static': round(us - u, 4), 'util_envoyScaled': round(u, 4)})
t6 = pd.DataFrame(rows)
print('\nEnvoy (update window 10 s-units): duty-cycle loss predicted vs measured (relative to static L = c)\n', t6.to_string(index=False))
t6.to_csv(os.path.join(OUT, 'e2_envoy_duty.csv'), index=False)
d = df[df.ctl == 'delta'].groupby(['S', 'dist'])[['eSd', 'nPairs', 'limitOverC', 'util', 'meanLatOverS']].mean().unstack('dist')
print('\nDelta across time scales\n', d.round(3).to_string())
