"""
Theory for "Noise, Not Capacity": rule-level and closed-form predictions.

Only (i) the service-time law and (ii) the published update rules are used here; no queue is simulated,
except where the exact saturated knee E[R](L) = s*max(1, L/c) enters (Lemma 1). The predictions are
compared with full discrete-event simulations of the real library code (harness/Sim.java).
Units: service times are normalised to mean 1.
"""
import math, os, random
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------- service-time laws (mean 1) ----------------
def sampler(dist, rng):
    if dist == 'det':
        return lambda n: np.ones(n)
    if dist == 'exp':
        return lambda n: rng.exponential(1.0, n)
    if dist in ('ln05', 'ln1', 'ln15'):
        s = {'ln05': 0.5, 'ln1': 1.0, 'ln15': 1.5}[dist]
        return lambda n: np.exp(-s * s / 2 + s * rng.standard_normal(n))
    if dist == 'par25':
        a = 2.5; xm = (a - 1) / a
        return lambda n: xm / (1 - rng.random(n)) ** (1 / a)
    # empirical law: data/svc_<name>.txt
    path = os.path.join(ROOT, 'data', f'svc_{dist}.txt')
    xs = np.array([float(l) for l in open(path) if l.strip() and not l.startswith('#')])
    xs = xs / xs.mean()
    return lambda n: xs[rng.integers(0, len(xs), n)]

_CV = {}
def cv(dist, n=2_000_000, seed=0):
    if (dist, n, seed) not in _CV:
        x = sampler(dist, np.random.default_rng(seed))(n)
        _CV[(dist, n, seed)] = float(x.std() / x.mean())
    return _CV[(dist, n, seed)]

def log10root(L):                       # Netflix Log10RootIntFunction(0)
    L = int(L)
    return max(1, int(math.log10(L))) if L >= 1 else 1

# ---------------- Proposition 3: VegasLimit (per-sample), uncongested regime ----------------
def vegas_rule_level(dist, nsamples=1_000_000, init=20, maxL=1000, seed=1):
    """Iterate the VegasLimit update rule (probe resets, running minimum, alpha/beta/threshold) on
    i.i.d. RTT samples R = S (no queueing: valid while L < c). Returns the time-average limit."""
    rng = np.random.default_rng(seed); S = sampler(dist, rng)(nsamples)
    L = float(init); m = 0.0; probeCount = 0; pr = random.Random(seed + 1); jitter = pr.uniform(0.5, 1.0)
    acc = 0.0; nacc = 0
    for i in range(nsamples):
        r = S[i]
        probeCount += 1
        if jitter * 30 * L <= probeCount:
            jitter = pr.uniform(0.5, 1.0); probeCount = 0; m = r
        elif m == 0 or r < m:
            m = r
        else:
            q = math.ceil(L * (1 - m / r))
            lg = log10root(L); alpha, beta, thr = 3 * lg, 6 * lg, lg
            if q <= thr: L += beta
            elif q < alpha: L += lg
            elif q > beta: L -= lg
            L = max(1, min(maxL, L))
        if i >= nsamples // 2:
            acc += L; nacc += 1
    return acc / nacc

def vegas_windowed_rule_level(dist, c, S_ms, T=None, Tw_s=1.0, init=20, maxL=1000, min_window=10, seed=1):
    """VegasLimit behind WindowedLimit (README-style 1-s windows, >= 10 samples per window), rule level.
    Window k holds n_k ~ Poisson(min(L,c) * Tw / s) completions (saturated throughput); its average RTT is
    (L/c - 1)^+ + mean of n_k service times (units of s; Lemma 1 wait plus sampled service). Windows with fewer
    than `min_window` samples are discarded, as in the library. Returns the time-average limit / c over the
    second half of T seconds (T defaults to the E2 run length max(600, 2 S_ms))."""
    T = T or max(600, int(2 * S_ms)); rng = np.random.default_rng(seed); draw = sampler(dist, rng)
    pr = random.Random(seed + 1); jitter = pr.uniform(0.5, 1.0)
    L = float(init); m = 0.0; probeCount = 0; acc = 0.0; nacc = 0
    s_s = S_ms / 1000.0
    for t in range(int(T / Tw_s)):
        n = rng.poisson(min(L, c) * Tw_s / s_s)
        if n >= min_window:
            mean_s = float(draw(n).mean()) if n <= 20000 else 1.0 + rng.standard_normal() * cv(dist) / math.sqrt(n)
            r = max(0.0, L / c - 1.0) + mean_s
            probeCount += 1
            if jitter * 30 * L <= probeCount:
                jitter = pr.uniform(0.5, 1.0); probeCount = 0; m = r
            elif m == 0 or r < m:
                m = r
            else:
                q = math.ceil(L * (1 - m / r))
                lg = log10root(L); alpha, beta, thr = 3 * lg, 6 * lg, lg
                if q <= thr: L += beta
                elif q < alpha: L += lg
                elif q > beta: L -= lg
                L = max(1, min(maxL, L))
        if t * Tw_s >= T / 2:
            acc += L; nacc += 1
    return acc / nacc / c

# ---------------- Proposition 4: Gradient2Limit ----------------
def g2_baseline_fixed_point(dist, n=400_000, seed=1, window=600):
    """Per-sample long-term EMA with the decay rule (B/R > 2 => B *= 0.95), iterated on i.i.d. R = S."""
    rng = np.random.default_rng(seed); S = sampler(dist, rng)(n)
    f = 2.0 / (window + 1); B = float(S[:10].mean()); acc = 0.0; k = 0
    for i in range(10, n):
        B = B * (1 - f) + S[i] * f
        if B / S[i] > 2: B *= 0.95
        if i > n // 2: acc += B; k += 1
    return acc / k

def g2_per_sample_equilibrium(dist, q=4.0, tol=1.5, minL=20, maxL=1000, seed=1):
    B = g2_baseline_fixed_point(dist, seed=seed)
    R = sampler(dist, np.random.default_rng(seed + 7))(1_000_000)
    one_minus_g = float(np.mean(1 - np.clip(tol * B / R, 0.5, 1.0)))
    Lstar = q / one_minus_g if one_minus_g > 0 else float('inf')
    return {'B': B, 'E1mg': one_minus_g, 'Lstar': Lstar, 'Lclamped': min(maxL, max(minL, Lstar))}

def g2w_drift(c, L0=20.0, T=3600, q=4.0, s=0.2, tol=1.5, window=600, maxL=1000, minL=20):
    """Gradient2 + WindowedLimit in saturation, one update per 1-s window, window-average RTT
    R_k = max(1, L_k/c) (units of mean service time; Lemma 1). Returns the limit trajectory."""
    f = 2.0 / (window + 1); L = L0; B = None; cnt = 0; ssum = 0.0; out = []
    for _ in range(T):
        R = max(1.0, L / c)
        if cnt < 10: cnt += 1; ssum += R; B = ssum / cnt
        else: B = B * (1 - f) + R * f
        if B / R > 2: B *= 0.95
        g = max(0.5, min(1.0, tol * B / R))
        L = max(minL, min(maxL, L * (1 - s) + (L * g + q) * s))
        out.append(L)
    return np.array(out)

def g2w_ramp_velocity(L, q=4.0, s=0.2, tol=1.5, window=600):
    """Quasi-steady growth per update in saturation above the knee: v = s(q+(tol-1)L)/(1+s*tol*lag),
    lag = (1-f)/f windows (steady-state lag of an EMA to a ramp)."""
    f = 2.0 / (window + 1); lag = (1 - f) / f
    return s * (q + (tol - 1) * L) / (1 + s * tol * lag)

# ---------------- Proposition 5: Envoy probe baseline ----------------
def envoy_probe_loss(S_ms, c, interval_ms=60000, jitter=0.15, n=50, min_conc=3):
    Tp = n * S_ms / min(min_conc, c)
    Ti = interval_ms * (1 + jitter / 2)
    phi = Tp / (Tp + Ti)
    return {'duty': phi, 'loss': phi * (1 - min_conc / c)}

def envoy_gc(c):
    """Critical gradient: below the knee the Envoy update L <- floor(Lg + sqrt(Lg)) with a constant gradient g < 1
    has the fixed point L = g/(1-g)^2; it lies below c iff g < g_c(c) = ((2c+1) - sqrt(4c+1)) / (2c)."""
    return ((2 * c + 1) - math.sqrt(4 * c + 1)) / (2 * c)

def envoy_epoch_util(ratio, c, buffer=0.25):
    """Predicted utilisation of a gradient epoch whose minRTT estimate is ratio * (true median):
    below the knee the window median equals the true median, g = (1+b)*ratio, the limit settles at g/(1-g)^2."""
    g = min(2.0, (1 + buffer) * ratio)
    if g >= envoy_gc(c):
        return 1.0
    return max(3.0, g / (1 - g) ** 2) / c

def envoy_minrtt_noise(dist, n=50, buffer=0.25, c=64, reps=200_000, seed=3):
    """Relative SD of the p50 of n service times, and the probability that an epoch is under-utilised:
    (1+buffer)*m_hat/median < g_c(c) (the burst headroom sqrt(Lg) is included through g_c)."""
    rng = np.random.default_rng(seed); draw = sampler(dist, rng)
    med = float(np.median(draw(4_000_000)))
    m = np.median(draw(n * reps).reshape(reps, n), axis=1)
    return {'median': med, 'rel_sd': float(np.std(m) / med), 'p_under': float(np.mean((1 + buffer) * m / med < envoy_gc(c))),
            'p_under_nohead': float(np.mean((1 + buffer) * m < med)),
            'exp_util': float(np.mean([envoy_epoch_util(r, c, buffer) for r in (m[:20000] / med)]))}

# ---------------- Theorem 7 / Propositions 9-10: Delta ----------------
def delta_elasticity(x, d=0.1, c=64):
    """Expected elasticity at base limit L = x*c for integer phase limits (Lemma 1 knee)."""
    L = x * c
    lm = max(1, math.floor(L * (1 - d))); lp = max(lm + 1, math.ceil(L * (1 + d)))
    return (math.log(max(lp, c)) - math.log(max(lm, c))) / (math.log(lp) - math.log(lm))

def delta_equilibrium(d=0.1, e_star=0.8):
    """Continuous-limit equilibrium L*/c = (1+d)^(e*-1) (1-d)^(-e*)."""
    return (1 + d) ** (e_star - 1) * (1 - d) ** (-e_star)

def delta_sd(cv_r, n, d=0.1):
    """Independent symmetric-arm special case of Proposition 9 (r_{+-}=0, v=1).

    The manuscript gives the dependence-aware form with within-phase variance
    inflation and cross-phase correlation. This helper is used only for the
    frozen-limit validation where the independence special case is compared
    with the simulated sampling law.
    """
    return math.sqrt(2.0 / n) * cv_r / math.log((1 + d) / (1 - d))

def delta_price(d=0.1, e_star=0.8):
    """Utilisation of the minus phase, mean RTT (units of s) of the plus phase, time-weighted
    utilisation and per-request mean RTT at equilibrium (saturated, continuous limits)."""
    um = ((1 - d) / (1 + d)) ** (1 - e_star)
    rp = ((1 + d) / (1 - d)) ** e_star
    util = 2 / (1 / um + 1)
    return {'util_minus': um, 'rtt_plus': rp, 'util': util, 'rtt': (1 + rp) / 2}

if __name__ == '__main__':
    for dist in ['det', 'ln05', 'exp', 'ln1', 'ln15', 'par25']:
        print(dist, 'cv=%.2f' % cv(dist), 'vegasL*=%.2f' % vegas_rule_level(dist, 600_000),
              'g2=%s' % {k: round(v, 3) for k, v in g2_per_sample_equilibrium(dist).items()})
