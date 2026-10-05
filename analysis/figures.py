"""Figures for the manuscript (results/figures/*.png, *.pdf).

Colour follows the entity in every figure (validated categorical palette, fixed slot order; see
dataviz reference palette): Delta = slot 1 blue, Envoy = 2 orange, failsafe-go = 3 aqua, Envoy with a
scaled window = 4 yellow, Vegas+W = 5 magenta, Gradient2+W = 6 green, Vegas = 7 violet, Gradient2 = 8 red.
The static oracle and theoretical predictions are drawn in neutral ink. Ordered quantities (server width,
offered load) use a single-hue ordinal blue ramp. Every plotted value is also in a table of the paper.
"""
import sys, os, math
import numpy as np, pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
HERE = os.path.dirname(__file__); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'theory'))
from load import load, good_rel
import theory as T

ROOT = os.path.join(HERE, '..'); FIG = os.path.join(ROOT, 'results', 'figures'); TAB = os.path.join(ROOT, 'results', 'tables')
os.makedirs(FIG, exist_ok=True)
INK, INK2, MUTED, AXIS = '#0b0b0b', '#52514e', '#898781', '#c3c2b7'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8.5, 'axes.titlesize': 8.5, 'axes.labelsize': 8.5,
                     'legend.fontsize': 8.0, 'xtick.labelsize': 8.0, 'ytick.labelsize': 8.0,
                     'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': AXIS, 'axes.linewidth': 0.6,
                     'xtick.color': INK2, 'ytick.color': INK2, 'axes.labelcolor': INK, 'text.color': INK,
                     'xtick.major.width': 0.6, 'ytick.major.width': 0.6, 'figure.dpi': 220, 'savefig.bbox': 'tight',
                     'pdf.fonttype': 42, 'ps.fonttype': 42,
                     'lines.linewidth': 1.4, 'legend.frameon': False, 'figure.facecolor': 'white', 'axes.facecolor': 'white'})
SLOT = {'delta': '#2a78d6', 'envoy': '#eb6834', 'failsafe': '#1baf7a', 'envoyScaled': '#eda100', 'vegasW': '#e87ba4',
        'g2W': '#008300', 'vegas': '#4a3aa7', 'g2': '#e34948'}
ORDER = ['delta', 'envoy', 'failsafe', 'envoyScaled', 'vegasW', 'g2W', 'vegas', 'g2']   # legend order = slot order
RAMP4 = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']     # ordinal blue, validated (--ordinal)
RAMP3 = ['#86b6ef', '#2a78d6', '#104281']
NAME = {'delta': 'Delta', 'envoy': 'Envoy', 'envoyScaled': 'Envoy, window 10s', 'failsafe': 'failsafe-go', 'vegas': 'Vegas',
        'vegasW': 'Vegas+W', 'g2': 'Gradient2', 'g2W': 'Gradient2+W (README)', 'grad': 'Gradient', 'gradW': 'Gradient+W',
        'aimd': 'AIMD', 'static': 'static L = c (oracle)'}

def save(fig, name):
    fig.savefig(os.path.join(FIG, name + '.png')); fig.savefig(os.path.join(FIG, name + '.pdf')); plt.close(fig); print('saved', name)

def endlabel(ax, x, y, text, color=INK2, dy=0.0, logy=False, **kw):
    ax.annotate(text, (x, y), xytext=(4, dy), textcoords='offset points', va='center', ha='left', fontsize=8.0, color=color, **kw)

# ---- Fig. 1: the knee (E0) and Delta's elasticity at a frozen limit (E7d) ----
def fig1():
    e0 = load('e0.txt'); e0 = e0[~e0.error]
    p = e0.tag.str.split(':', expand=True); e0['L'] = p[4].astype(float); e0['rho_'] = p[3].astype(float)
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.55))
    x = np.linspace(0.5, 2.0, 200)
    ax[0].plot(x, np.maximum(1, x), color=INK, lw=1.0, ls='--', label='Lemma 1, saturated', zorder=5)
    st = {'det': '-', 'exp': (0, (4, 1.5)), 'ln1': (0, (1, 1.2))}
    for k, rho in enumerate([1.2, 2.0, 5.0]):
        for dist in ['det', 'exp', 'ln1']:
            d = e0[(e0.dist == dist) & (e0.rho_ == rho)].sort_values('L')
            ax[0].plot(d.L / 64, d.meanLatOverS, linestyle=st[dist], color=RAMP3[k], lw=1.3,
                       label=(f'ρ = {rho:g}' if dist == 'det' else None))
    ax[0].set_xlabel('limit L / c'); ax[0].set_ylabel('mean RTT / s')
    ax[0].set_title('(a) static limits, c = 64 (three laws per load)', loc='left', fontsize=8.0)
    ax[0].legend(loc='upper left'); ax[0].set_xlim(0.5, 2.0); ax[0].set_ylim(0.9, 2.1)
    tc = pd.read_csv(os.path.join(TAB, 'e7d_curve.csv'))
    xx = np.linspace(0.8, 1.4, 241)
    ax[1].plot(xx, [T.delta_elasticity(v) for v in xx], color=INK, lw=1.0, ls='--', label='Theorem 7 (ρ → ∞, integer limits)')
    mk = {'det': 's', 'exp': 'o', 'ln1': '^'}; lab = {'det': 'deterministic', 'exp': 'exponential', 'ln1': 'lognormal σ = 1'}
    for dist in ['det', 'exp', 'ln1']:
        d = tc[tc.law == dist]
        ax[1].plot(d.L_over_c, d.e_sim, mk[dist], ms=4.2, mfc='white', mec=SLOT['delta'], mew=1.1, label=f'Delta, {lab[dist]}')
    ax[1].axhline(0.8, color=MUTED, lw=0.6); ax[1].text(0.805, 0.83, 'target e* = 0.8', fontsize=8.0, color=INK2)
    ax[1].set_xlabel('base limit L / c (dither ±10%)'); ax[1].set_ylabel('elasticity estimate ê')
    ax[1].set_title('(b) Delta at a frozen limit, ρ = 2, c = 64', loc='left', fontsize=8.0)
    ax[1].legend(loc='lower right'); fig.tight_layout(); save(fig, 'fig1_knee')

# ---- Fig. 2: main grid, small multiples (one panel per controller; colour = server width) ----
def fig2():
    e1 = load('e1_main.txt'); e1['g'] = good_rel(e1, ['c', 'dist'])
    order = ['delta', 'envoy', 'failsafe', 'vegasW', 'vegas', 'g2W', 'g2', 'gradW', 'grad', 'aimd', 'static']
    fig, axs = plt.subplots(2, 6, figsize=(7.2, 3.2), sharex=True, sharey=True)
    markers = {4: 'o', 16: 's', 64: '^', 256: 'D'}
    for ax, a in zip(axs.flat, order):
        ax.axhline(1.5, color=MUTED, lw=0.5)
        d = e1[e1.ctl == a]
        for k, c in enumerate([4, 16, 64, 256]):
            x = d[d.c == c]
            ax.scatter(x.util, x.meanLatOverS.clip(upper=300), s=18, marker=markers[c],
                       facecolor=RAMP4[k], edgecolor=INK, linewidth=0.45,
                       label=f'c = {c}', zorder=3)
        nm = NAME[a].replace(' (README)', '').replace(' (oracle)', '')
        ax.set_title(f'{nm}\n{int(d.g.sum())}/60 good', fontsize=8.0, color=INK)
        ax.set_yscale('log'); ax.set_ylim(0.8, 400); ax.set_xlim(-0.03, 1.05)
        ax.set_xticks([0, 0.5, 1]); ax.set_xticklabels(['0', '0.5', '1'])
    axs.flat[-1].axis('off')
    h, l = axs.flat[0].get_legend_handles_labels()
    axs.flat[-1].legend(h, l, loc='center', title='server width', title_fontsize=8.0)
    for ax in axs[1, :]: ax.set_xlabel('utilisation')
    for ax in axs[:, 0]: ax.set_ylabel('mean RTT / s')
    fig.tight_layout(h_pad=0.6, w_pad=0.3); save(fig, 'fig3_grid')

# ---- Fig. 3: time scale (E2) ----
def fig3():
    e2 = load('e2.txt')
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.55))
    series = ['delta', 'envoy', 'failsafe', 'envoyScaled', 'vegasW', 'g2W']
    for a in series + ['static']:
        g = e2[e2.ctl == a].groupby('S')[['util', 'meanLatOverS']].mean()
        if a == 'static':
            kw = dict(color=INK2, lw=0.9, ls='--', marker=None)
        else:
            kw = dict(color=SLOT[a], lw=2.0 if a == 'delta' else 1.2, marker='o', ms=3.2, mec='white', mew=0.5)
        ax[0].plot(g.index, g.util, label=NAME[a], **kw); ax[1].plot(g.index, g.meanLatOverS, **kw)
        if a in ('g2W', 'envoy', 'failsafe', 'envoyScaled'):     # selective direct labels; the legend in (a) carries the rest
            endlabel(ax[1], g.index[-1], g.meanLatOverS.iloc[-1], NAME[a].replace(' (README)', ''))
    for x in ax:
        x.set_xscale('log'); x.set_xlabel('mean service time s (ms, log scale)')
        x.set_xticks([1, 10, 100, 1000, 5000]); x.set_xticklabels(['1', '10', '100', '1000', '5000'])
    ax[0].set_ylabel('utilisation'); ax[0].set_ylim(0, 1.05); ax[1].set_ylabel('mean RTT / s (log scale)'); ax[1].set_yscale('log')
    ax[1].set_xlim(0.7, 5000 * 3.5)
    ax[0].set_title('(a) utilisation, c = 64, ρ = 2', loc='left'); ax[1].set_title('(b) mean latency', loc='left')
    ax[0].legend(loc='lower left', ncol=1); fig.tight_layout(); save(fig, 'fig4_timescale')

# ---- Fig. 4: dynamics (E3 capacity step, slow load ramp) ----
def fig4():
    fig, ax = plt.subplots(2, 2, figsize=(7.2, 3.9), sharex='col')
    series = ['delta', 'envoy', 'failsafe', 'vegasW', 'g2W']
    for col, sc in enumerate(['cap', 'ramp']):
        last = {}
        for a in series:
            f = os.path.join(ROOT, 'results', 'ts', f'e3_{a}_{sc}_1.csv')
            if not os.path.exists(f): continue
            d = pd.read_csv(f)
            lim = (d['limit'] / d.c).rolling(10, center=True, min_periods=1).mean()
            lat = (d.mean_rtt_ms / (10 * d.s_scale)).rolling(10, center=True, min_periods=1).mean()
            kw = dict(color=SLOT[a], lw=1.7 if a == 'delta' else 0.9, zorder=4 if a == 'delta' else 2)
            ax[0, col].plot(d.t_s, lim, label=NAME[a], **kw); ax[1, col].plot(d.t_s, lat, **kw)
            last[a] = (d.t_s.iloc[-1], lim.iloc[-1], lat.iloc[-1])
        for t0 in ([600, 1200] if sc == 'cap' else [900]):
            for r in (0, 1): ax[r, col].axvline(t0, color=AXIS, lw=0.6, zorder=0)
        for r in (0, 1): ax[r, col].set_yscale('log')
        ax[1, col].set_xlabel('time (s)')
        ax[0, col].set_ylabel('limit / current capacity'); ax[1, col].set_ylabel('mean RTT / current s')
    ax[0, 0].set_title('(a) capacity 64 → 32 at 600 s, back at 1,200 s (ρ = 2)', loc='left')
    ax[0, 1].set_title('(b) load ramp ρ = 0.5 → 1.5 → 0.5 (peak at 900 s)', loc='left')
    ax[0, 0].legend(loc='upper left', ncol=3); fig.tight_layout(); save(fig, 'fig5_dynamics')

# ---- Fig. 5: Envoy epochs (E7c) and Gradient2 drift (E7b) ----
def fig5():
    ep = pd.read_csv(os.path.join(TAB, 'e7c_epochs.csv'))
    fig, ax = plt.subplots(1, 2, figsize=(7.0, 2.55))
    mk = {'exp': 'o', 'ln1': '^', 'ln15': 's', 'ln05': 'D', 'par25': 'v'}
    lab = {'exp': 'exponential', 'ln1': 'lognormal σ = 1', 'ln15': 'lognormal σ = 1.5', 'ln05': 'lognormal σ = 0.5', 'par25': 'Pareto α = 2.5'}
    for dist in ['exp', 'ln1', 'ln15', 'ln05', 'par25']:
        d = ep[ep.dist == dist]
        ax[0].scatter(d.ratio, d.util, s=9, marker=mk[dist], facecolor='white', edgecolor=SLOT['envoy'], linewidth=0.7, label=f'Envoy epoch, {lab[dist]}', zorder=3)
    x = np.linspace(0.45, 1.9, 600)
    ax[0].plot(x, [T.envoy_epoch_util(v, 64) for v in x], color=INK, lw=1.0, ls='--', label='Proposition 5(ii)', zorder=4)
    ax[0].axvline(T.envoy_gc(64) / 1.25, color=AXIS, lw=0.6, zorder=0)
    ax[0].text(T.envoy_gc(64) / 1.25 + 0.015, 0.05, 'm̂/μ = 0.706', fontsize=8.0, color=INK2)
    ax[0].set_xlabel('minRTT estimate / true median (m̂/μ)'); ax[0].set_ylabel('utilisation of the epoch')
    ax[0].set_title('(a) Envoy: 808 epochs, c = 64, s = 10 ms', loc='left'); ax[0].legend(loc='lower right', fontsize=8.0)
    tsd = os.path.join(ROOT, 'results', 'ts')
    for c, dy in [(8, -6), (64, 6)]:
        for seed in [1, 2, 3]:
            f = os.path.join(tsd, f'e7b_g2W_{c}_{seed}.csv')
            if os.path.exists(f):
                d = pd.read_csv(f); ax[1].plot(d.t_s, d['limit'], color=SLOT['g2W'], lw=0.8, alpha=0.9,
                                               label=('Gradient2+W, simulated (3 seeds)' if (c == 8 and seed == 1) else None))
        ode = T.g2w_drift(c, T=3600); ax[1].plot(np.arange(1, 3601), ode, color=INK, lw=0.9, ls='--', label=('recursion (2)' if c == 8 else None))
        ax[1].annotate(f'c = {c}', (1200, ode[1199]), xytext=(6, dy), textcoords='offset points', fontsize=8.0, color=INK2)
    ax[1].set_xlabel('time (s)'); ax[1].set_ylabel('limit (log scale)'); ax[1].set_yscale('log')
    ax[1].set_title('(b) Gradient2 + WindowedLimit (README), ρ = 2', loc='left'); ax[1].legend(loc='lower right')
    fig.tight_layout(); save(fig, 'fig2_envoy_g2w')

if __name__ == '__main__':
    which = sys.argv[1:] or ['1', '2', '3', '4', '5']
    for w in which:
        try:
            {'1': fig1, '2': fig2, '3': fig3, '4': fig4, '5': fig5}[w]()
        except Exception as ex:
            import traceback; traceback.print_exc(); print('figure', w, 'failed:', repr(ex))
