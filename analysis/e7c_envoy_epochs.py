"""E7c: Envoy per-epoch analysis. Each minRTT window (logged with its median m_hat) starts an epoch that lasts until
the next window; the epoch's utilisation is compared with the prediction of Proposition 5(ii):
u = min(1, g/((1-g)^2 c)) with g = (1+b) m_hat / median, i.e. under-utilisation iff g < g_c(c)."""
import sys, os, math
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'theory'))
import theory as T

ROOT = os.path.join(os.path.dirname(__file__), '..')
OUT = os.path.join(ROOT, 'results', 'tables')
C, S_MS = 64, 10.0
rows = []
for dist in ['exp', 'ln1', 'ln05', 'ln15', 'par25']:
    med = T.envoy_minrtt_noise(dist, reps=2000)['median'] * S_MS          # true median service time (ms)
    for seed in [1, 2, 3]:
        base = os.path.join(ROOT, 'results', 'ts', f'e7c_envoy_{dist}_{seed}')
        ts = pd.read_csv(base + '.csv'); ep = pd.read_csv(base + '_epochs.csv')
        ts['util'] = ts.completions * (S_MS / 1000.0) / ts.c
        for k in range(1, len(ep) - 1):                    # skip the start-up window and the last (truncated) epoch
            a, b = ep.window_end_s.iloc[k], ep.window_start_s.iloc[k + 1]
            w = ts[(ts.t_s > math.ceil(a) + 1) & (ts.t_s <= math.floor(b))]
            if len(w) < 20: continue
            ratio = ep.minrtt_ms.iloc[k] / med
            rows.append({'dist': dist, 'seed': seed, 'epoch': k, 'ratio': ratio, 'util': w.util.mean(),
                         'pred': T.envoy_epoch_util(ratio, C), 'limit_mean': ts[(ts.t_s > math.ceil(a) + 1) & (ts.t_s <= math.floor(b))]['limit'].mean()})
df = pd.DataFrame(rows)
df.to_csv(os.path.join(OUT, 'e7c_epochs.csv'), index=False)
summ = []
for dist, g in df.groupby('dist', sort=False):
    th = T.envoy_minrtt_noise(dist)
    summ.append({'law': dist, 'epochs': len(g), 'rel_sd_pred': round(th['rel_sd'], 3), 'rel_sd_meas': round(float(g.ratio.std() / g.ratio.mean()), 3),
                 'p_under_pred': round(th['p_under'], 3), 'p_under_meas': round(float((g.util < 0.95).mean()), 3),
                 'util_pred': round(th['exp_util'], 3), 'util_meas': round(float(g.util.mean()), 3),
                 'corr_pred_meas': round(float(np.corrcoef(g.pred, g.util)[0, 1]), 3) if g.pred.std() > 0 else float('nan'),
                 'mae_under_epochs': round(float((g[g.pred < 1].util - g[g.pred < 1].pred).abs().mean()), 3) if (g.pred < 1).any() else float('nan')})
summ = pd.DataFrame(summ)
pd.set_option('display.width', 250)
print(summ.to_string(index=False))
summ.to_csv(os.path.join(OUT, 'e7c_summary.csv'), index=False)
# binned relation between the baseline ratio and epoch utilisation (all laws pooled)
bins = [0, 0.6, 0.65, 0.7, 0.75, 0.8, 0.9, 1.0, 1.2, 10]
df['bin'] = pd.cut(df.ratio, bins)
print(df.groupby('bin', observed=True).agg(n=('util', 'size'), util_meas=('util', 'mean'), util_pred=('pred', 'mean')).round(3).to_string())
