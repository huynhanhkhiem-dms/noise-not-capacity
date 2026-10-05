import java.util.*;

/**
 * Delta: an excitation-based adaptive concurrency limiter.
 *
 * Instead of comparing latency with a baseline, Delta identifies the latency knee of the service with a
 * randomized, exogenous, multiplicative perturbation of the limit:
 *
 *   - Each "pair" runs two phases, at L(1-d) and L(1+d), in random order (a two-arm randomized experiment).
 *   - A phase has three stages at a constant limit:
 *       SETTLE : the first `lim` admissions are not measured; this reduces phase carry-over but does not
 *                guarantee that every request admitted under the preceding phase has departed;
 *       COUNT  : the next max(nMin, nPerL*lim) admissions are measured;
 *       DRAIN  : admissions continue at the same limit (not measured) until every measured request
 *                has completed, so every measured request lives its whole life under one limit.
 *   - Log-elasticity of mean RTT with respect to the limit:
 *         e = (ln mean R+ - ln mean R-) / (ln L+ - ln L-)
 *     In a saturated c-server system E[R](L) = s * max(1, L/c) (exact, Little's law), so e = 0 below the
 *     knee, 1 above it, and ln(L+/c)/ln(L+/L-) while the dither straddles c.
 *   - Robbins-Monro update in log space: ln L <- ln L + gamma * (eStar - e), step clipped to +-maxStep.
 *   - The identification theorem is conditional on stationary saturation at each fixed phase limit.
 *     The implementation cannot certify saturation from latency alone. A rejection proves only that the
 *     gate was closed at that instant, so the practical update gate is deliberately conservative: a pair
 *     updates only if at least one arrival was rejected during COUNT in BOTH phases. This is an empirical
 *     safeguard against underloaded updates, not a certificate of the theorem's saturation assumption.
 *     In the theorem's limiting saturated regime, excess arrivals make this gate automatically satisfied;
 *     at finite offered load it can suppress a base-limit update but the elasticity estimate is still logged.
 *
 * No absolute time constant is used: everything is counted in admissions/completions (scale invariance).
 * Ablation switches (all false in the evaluated design): fixedOrder, noSettle, noDrain, geoMean, and
 * anyReject (legacy ablation: any rejection anywhere in the pair).
 */
public final class Delta {
    final double d, eStar, gamma, maxStep;
    final int nMin, minL, maxL;
    double nPerL = 0;
    boolean fixedOrder = false, noSettle = false, noDrain = false, geoMean = false, anyReject = false;

    double L;
    int out = 0;
    long updates = 0;
    double lastE = Double.NaN;
    double sumE = 0, sumE2 = 0; long nE = 0;
    double sumCv = 0; long nCv = 0;          // diagnostics: pooled within-phase CV of RTT
    final SplittableRandom rnd;

    private static final int SETTLE = 0, COUNT = 1, DRAIN = 2;

    static final class Pair {
        final int[] order = new int[2], lim = new int[2];
        final long[] counted = new long[2], completed = new long[2], blocked = new long[2], blockedCount = new long[2];
        final double[] sum = new double[2], sumSq = new double[2];
        int phaseIdx = 0, stage = SETTLE;
        long admittedInPhase = 0;
        boolean admissionsClosed = false;       // both phases have closed their COUNT stage
    }
    private final ArrayDeque<Pair> open = new ArrayDeque<>();   // pairs with outstanding measured requests
    private Pair cur;

    public Delta(double initL, double d, double eStar, double gamma, int nMin, int minL, int maxL, long seed) {
        this.L = initL; this.d = d; this.eStar = eStar; this.gamma = gamma; this.nMin = nMin;
        this.minL = minL; this.maxL = maxL; this.maxStep = 0.25;
        this.rnd = new SplittableRandom(seed ^ 0x9E3779B97F4A7C15L);
        cur = newPair();
    }

    private Pair newPair() {
        Pair p = new Pair();
        boolean minusFirst = fixedOrder || rnd.nextBoolean();
        p.order[0] = minusFirst ? 0 : 1; p.order[1] = minusFirst ? 1 : 0;
        p.lim[0] = Math.max(minL, (int) Math.floor(L * (1 - d)));
        p.lim[1] = Math.min(maxL, Math.max(p.lim[0] + 1, (int) Math.ceil(L * (1 + d))));
        open.add(p);
        return p;
    }

    private int type() { return cur.order[cur.phaseIdx]; }

    public int limit() { return cur.lim[type()]; }

    public boolean admit() {
        if (out < cur.lim[type()]) { out++; return true; }
        cur.blocked[type()]++;
        if (cur.stage == COUNT) cur.blockedCount[type()]++;
        return false;
    }

    /** token for the request just admitted: {pair, type} if measured, else null. */
    public Object token() {
        Pair p = cur; int ty = type();
        p.admittedInPhase++;
        if (p.stage == SETTLE && (noSettle || p.admittedInPhase > p.lim[ty])) p.stage = COUNT;
        if (p.stage != COUNT) return null;
        p.counted[ty]++;
        Object[] tok = {p, ty};
        if (p.counted[ty] >= Math.max(nMin, (long) Math.ceil(nPerL * p.lim[ty]))) {
            p.stage = DRAIN;
            if (noDrain) closePhase(p);
        }
        return tok;
    }

    public void done(Object tok, long rttNs) {
        out--;
        if (tok == null) return;
        Object[] t = (Object[]) tok;
        Pair p = (Pair) t[0]; int ty = (Integer) t[1];
        p.sum[ty] += geoMean ? Math.log(rttNs) : rttNs; p.sumSq[ty] += (double) rttNs * rttNs; p.completed[ty]++;
        if (!noDrain && p == cur && p.stage == DRAIN && ty == type() && p.completed[ty] == p.counted[ty]) closePhase(p);
        finalizeReady();
    }

    /** end the current phase of the current pair (after its drain, or immediately with noDrain). */
    private void closePhase(Pair p) {
        if (p != cur) return;
        if (p.phaseIdx == 0) { p.phaseIdx = 1; p.stage = SETTLE; p.admittedInPhase = 0; return; }
        p.admissionsClosed = true;
        finalizeReady();                      // with DRAIN the pair is complete: update L before the next pair
        cur = newPair();
    }

    private void finalizeReady() {
        while (!open.isEmpty()) {
            Pair q = open.peek();
            if (!q.admissionsClosed || q.completed[0] < q.counted[0] || q.completed[1] < q.counted[1]) break;
            open.poll();
            update(q);
        }
    }

    private void update(Pair q) {
        double mMinus = q.sum[0] / q.completed[0], mPlus = q.sum[1] / q.completed[1];
        double num = geoMean ? (mPlus - mMinus) : (Math.log(mPlus) - Math.log(mMinus));
        double e = num / (Math.log(q.lim[1]) - Math.log(q.lim[0]));
        boolean binding = anyReject ? q.blocked[0] + q.blocked[1] > 0            // first design (ablation)
                                    : q.blockedCount[0] > 0 && q.blockedCount[1] > 0; // conservative rejection-based update gate
        double step = binding ? gamma * (eStar - e) : 0.0;
        step = Math.max(-maxStep, Math.min(maxStep, step));
        L = Math.max(minL, Math.min(maxL, L * Math.exp(step)));
        lastE = e; updates++; sumE += e; sumE2 += e * e; nE++;
        if (!geoMean) for (int k = 0; k < 2; k++) { double m = q.sum[k] / q.completed[k]; double v = q.sumSq[k] / q.completed[k] - m * m; if (m > 0 && v >= 0) { sumCv += Math.sqrt(v) / m; nCv++; } }
    }
}
