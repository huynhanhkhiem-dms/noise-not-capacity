"""Headline counts: runs in the good region across the stationary experiments E1, E2, E4, E6, E8."""
import sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(__file__))
from load import load, good_rel
parts = []
for name, keys in [('e1_main.txt', ['c', 'dist']), ('e2.txt', ['S', 'dist']), ('e4.txt', ['law', 'c']), ('e6.txt', ['rho']), ('e8.txt', ['dist'])]:
    d = load(name)
    if name == 'e4.txt': d['law'] = d.tag.str.split(':').str[2]
    d['g'] = good_rel(d, keys); d['exp'] = name.split('.')[0].replace('_main', '')
    parts.append(d[['exp', 'ctl', 'g', 'util', 'meanLatOverS']])
a = pd.concat(parts, ignore_index=True)
t = a.groupby(['ctl', 'exp']).g.agg(['sum', 'size']).unstack('exp')
tot = a.groupby('ctl').g.agg(good='sum', runs='size'); tot['share'] = (tot.good / tot.runs).round(3)
pd.set_option('display.width', 200)
print(t.to_string()); print(tot.sort_values('share', ascending=False).to_string())
print('total runs in these five experiments:', len(a), '; all experiments incl. E0,E3,E4b,E4c,E5,E7,E7c,E9:',
      sum(sum(1 for l in open(os.path.join(os.path.dirname(__file__), '..', 'results', f)) if l.startswith('TAG '))
          for f in ['e0.txt', 'e1_main.txt', 'e2.txt', 'e3.txt', 'e4.txt', 'e4b.txt', 'e4c.txt', 'e5.txt', 'e6.txt', 'e7.txt', 'e7c.txt', 'e8.txt', 'e9.txt', 'e9sim.txt']))
tot.to_csv(os.path.join(os.path.dirname(__file__), '..', 'results', 'tables', 'headline.csv'))
