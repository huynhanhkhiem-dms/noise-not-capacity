import java.util.*;

/**
 * Faithful Java port of Envoy's adaptive-concurrency GradientController
 * (source/extensions/filters/http/adaptive_concurrency/controller/gradient_controller.cc,
 *  envoy commit b71f63bd875e1df93ea68e04e9fb788dd967a611).
 *
 * Differences from the C++ original that do not change the control law:
 *  - time is the simulated clock of the harness (ns);
 *  - the latency histogram is an exact sample buffer (the original uses an approximate
 *    libcircllhist quantile; we use the exact empirical quantile);
 *  - timers are delivered by the harness event queue.
 */
public final class Envoy {
    // ---- configuration (defaults from gradient_controller.cc) ----
    final long sampleIntervalNs;       // concurrency_update_interval (no default in Envoy; typical 100ms)
    final long minRttIntervalNs;       // min_rtt_calc_params.interval (typical 60s)
    final double jitterPct;            // default 15%
    final int maxLimit;                // default 1000
    final int minRttRequestCount;      // default 50
    final double percentile;           // default 0.50
    final int minConcurrency;          // default 3
    final int minConcurrencyLimit;     // defaults to min_concurrency
    final double bufferPct;            // default 25%

    // ---- state ----
    int limit;                          // concurrency_limit_
    int deferredLimit = 0;              // deferred_limit_value_
    int outstanding = 0;                // num_rq_outstanding_
    long minRttNs = 0, sampleRttNs = 0;
    long minRttEpoch = 0;
    boolean inMinRttWindow = false;
    int consecutiveMinSet = 0;
    final ArrayList<Long> hist = new ArrayList<>();
    final SplittableRandom rnd;
    java.io.PrintWriter epochLog = null;  // optional diagnostics: one line per completed minRTT window (no effect on control)

    // timers: the harness polls these deadlines
    long nextSampleReset = Long.MAX_VALUE, nextMinRtt = Long.MAX_VALUE;

    Envoy(long sampleIntervalNs, long minRttIntervalNs, int maxLimit, int minRttRequestCount, double percentile, long seed) {
        this(sampleIntervalNs, minRttIntervalNs, maxLimit, minRttRequestCount, percentile, seed, 0.15, 0.25, 3);
    }

    Envoy(long sampleIntervalNs, long minRttIntervalNs, int maxLimit, int minRttRequestCount, double percentile, long seed,
          double jitterPct, double bufferPct, int minConcurrency) {
        this.jitterPct = jitterPct; this.bufferPct = bufferPct; this.minConcurrency = minConcurrency; this.minConcurrencyLimit = minConcurrency;
        this.sampleIntervalNs = sampleIntervalNs; this.minRttIntervalNs = minRttIntervalNs;
        this.maxLimit = maxLimit; this.minRttRequestCount = minRttRequestCount; this.percentile = percentile;
        this.rnd = new SplittableRandom(seed ^ 0x5DEECE66DL);
        this.limit = minConcurrency;                 // constructor: min-RTT sampling enabled -> minRTTCalcConcurrency
    }

    void start(long now) { enterMinRttWindow(now); nextSampleReset = now + sampleIntervalNs; }

    boolean admit() { if (outstanding < limit) { outstanding++; return true; } return false; }

    void onDone(long sendTime, long now) {
        outstanding--;
        if (sendTime < minRttEpoch) return;            // disregard samples from previous minRTT window
        hist.add(now - sendTime);
        updateMinRtt(now);
    }

    void onTimers(long now) {
        if (now >= nextMinRtt) { nextMinRtt = Long.MAX_VALUE; enterMinRttWindow(now); }
        if (now >= nextSampleReset) {
            if (inMinRttWindow) { nextSampleReset = Long.MAX_VALUE; return; } // give up; re-enabled after minRTT calc
            resetSampleWindow();
            nextSampleReset = now + sampleIntervalNs;
        }
    }

    long nextTimer() { return Math.min(nextMinRtt, nextSampleReset); }

    private void enterMinRttWindow(long now) {
        if (inMinRttWindow) return;
        inMinRttWindow = true;
        deferredLimit = limit;
        updateLimit(Math.min(limit, minConcurrency), now);
        hist.clear();
        minRttEpoch = now;
    }

    private void updateMinRtt(long now) {
        if (!inMinRttWindow || hist.size() < minRttRequestCount) return;
        minRttNs = quantileAndClear();
        if (epochLog != null) epochLog.printf(Locale.ROOT, "%.6f,%.6f,%.6f,%d%n", minRttEpoch / 1e9, now / 1e9, minRttNs / 1e6, deferredLimit);
        inMinRttWindow = false;
        updateLimit(deferredLimit, now);
        deferredLimit = 0;
        long iv = minRttIntervalNs;
        long jitterRange = (long) Math.ceil(iv / 1e6 * jitterPct);           // ms
        long jitter = jitterRange > 0 ? (rnd.nextLong(Long.MAX_VALUE) % jitterRange) : 0;
        nextMinRtt = now + iv + jitter * 1_000_000L;
        nextSampleReset = now + sampleIntervalNs;
    }

    private void resetSampleWindow() {
        if (hist.isEmpty()) return;
        sampleRttNs = quantileAndClear();
        updateLimit(calculateNewLimit(), -1);
    }

    private long quantileAndClear() {
        long[] a = new long[hist.size()]; for (int i = 0; i < a.length; i++) a[i] = hist.get(i);
        Arrays.sort(a);
        double pos = percentile * (a.length - 1); int lo = (int) Math.floor(pos); int hi = Math.min(a.length - 1, lo + 1);
        double q = a[lo] + (pos - lo) * (a[hi] - a[lo]);
        hist.clear();
        return Math.max(1L, (long) q);
    }

    private int calculateNewLimit() {
        double bufferedMinRtt = minRttNs + minRttNs * bufferPct;
        double rawGradient = bufferedMinRtt / sampleRttNs;
        double gradient = Math.max(0.5, Math.min(2.0, rawGradient));
        double l = limit * gradient;
        double burstHeadroom = Math.sqrt(l);
        long newLimit = (long) (l + burstHeadroom);                         // uint32 truncation
        return (int) Math.max(minConcurrencyLimit, Math.min(maxLimit, newLimit));
    }

    private void updateLimit(int newLimit, long now) {
        int old = limit;
        limit = newLimit;
        if (!inMinRttWindow && old == minConcurrencyLimit && newLimit == minConcurrencyLimit) consecutiveMinSet++;
        else consecutiveMinSet = 0;
        if (consecutiveMinSet >= 5 && now >= 0) nextMinRtt = now;   // re-measure minRTT immediately
        else if (consecutiveMinSet >= 5) nextMinRtt = 0;           // fire at next harness poll
    }
}
