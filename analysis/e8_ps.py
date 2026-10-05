"""E8: processor-sharing server (c = 64 cores, s = 10 ms, rho = 2)."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, LABEL, good_rel

OUT = os.path.join(os.path.dirname(__file__), '..', 'results', 'tables')
df = load('e8.txt'); assert not df['error'].any()
order = ['vegas', 'vegasW', 'g2', 'g2W', 'grad', 'gradW', 'aimd', 'envoy', 'failsafe', 'delta', 'static']
df['good'] = good_rel(df, ['dist'])
t = df.groupby(['ctl', 'dist'])[['util', 'meanLatOverS', 'p99OverS', 'limitOverC']].mean().unstack('dist')
t = t.reindex([o for o in order if o in set(df.ctl)])
pd.set_option('display.width', 250)
print(t.round(3).to_string())
t.round(4).to_csv(os.path.join(OUT, 'e8_ps.csv'))
