"""E6: offered-load sensitivity (rho = 0.5 .. 5; c = 64, s = 10 ms, exp)."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, LABEL

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
df = load('e6.txt'); assert not df['error'].any()
order = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'failsafe', 'delta', 'deltaAny', 'static']
df['utilRel'] = df['util'] / df['rho'].clip(upper=1.0)   # utilisation relative to what the load allows
pd.set_option('display.width', 250)
for m in ['utilRel', 'meanLatOverS', 'excessReject', 'limitOverC']:
    t = df.groupby(['ctl', 'rho'])[m].mean().unstack('ctl')[[o for o in order if o in set(df.ctl)]]
    print(f'\n{m}\n', t.round(3).to_string())
    t.round(4).to_csv(os.path.join(OUT, f'e6_{m}.csv'))
