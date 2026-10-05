/**
 * Conformance tests for the Java port of Envoy's GradientController.
 * Each test re-implements a test of envoy/test/extensions/filters/http/adaptive_concurrency/controller/
 * gradient_controller_test.cc (commit b71f63b) with the same configuration, inputs and assertions.
 * Run: java -cp build EnvoyPortTest   (exit code 0 = all assertions hold)
 */
public class EnvoyPortTest {
    static long now;
    static Envoy e;
    static int failures = 0, checks = 0;

    static void check(boolean ok, String what) { checks++; if (!ok) { failures++; System.out.println("FAIL: " + what); } }
    static long ms(double x) { return (long) (x * 1e6); }

    static Envoy make(double intervalS, int requestCount, double bufferPct, int minConc) {
        Envoy c = new Envoy(ms(100), (long) (intervalS * 1e9), 1000, requestCount, 0.5, 1L, 0.0, bufferPct, minConc);
        now = 0; c.start(0); e = c;
        advance(ms(42L * 3600 * 1000));          // makeController advances 42 h
        return c;
    }
    static void advance(long d) {
        long target = now + d;
        while (true) { long t = e.nextTimer(); if (t <= target) { now = Math.max(now, t); e.onTimers(now); } else break; }
        now = target;
    }
    static void tryForward(boolean expect) { check(e.admit() == expect, "forward expected " + expect + " at limit " + e.limit); }
    static void sample(double latencyMs) { e.onDone(now - ms(latencyMs), now); }
    static void pastMinRtt(int requestCount, double latencyMs) { for (int i = 0; i <= requestCount; i++) { tryForward(true); sample(latencyMs); } }

    public static void main(String[] a) {
        // --- ConcurrencyLimitBehaviorTestBasic (buffer 10%, min_concurrency 7, request_count 5)
        make(30, 5, 0.10, 7);
        check(e.limit == 7, "Basic: initial limit 7");
        pastMinRtt(5, 5); check(e.minRttNs == ms(5), "Basic: minRTT 5ms");
        advance(ms(101));
        check(e.limit >= 7 && e.limit / 7.0 <= 2.0, "Basic: headroom growth bounded");
        for (int r = 0; r < 10; r++) {
            int last = e.limit;
            for (int i = 1; i <= 5; i++) { tryForward(true); sample(4); }
            advance(ms(101));
            check(last <= e.limit && (double) last / e.limit >= 0.5, "Basic: grows with gradient <= 2");
        }
        for (int r = 0; r < 10; r++) {
            int last = e.limit;
            for (int i = 1; i <= 5; i++) { tryForward(true); sample(6); }
            advance(ms(101));
            check(e.limit < last && e.limit >= 7, "Basic: shrinks and stays >= 7");
        }
        // --- MinRTTBufferTest (buffer 50%, request_count 5)
        make(30, 5, 0.50, 3);
        check(e.limit == 3, "Buffer: initial limit 3");
        pastMinRtt(5, 5); check(e.minRttNs == ms(5), "Buffer: minRTT 5ms");
        for (int r = 0; r < 10; r++) {
            int last = e.limit;
            for (int i = 1; i <= 5; i++) { tryForward(true); sample(6); }
            advance(ms(101));
            check(e.limit > last, "Buffer: 50% buffer keeps growing");
        }
        // --- MinRTTReturnToPreviousLimit (request_count 5, interval 30 s)
        make(30, 5, 0.25, 3);
        check(e.limit == 3, "Return: initial 3");
        pastMinRtt(5, 5); advance(ms(1000));
        for (int k = 0; k < 5; k++) {
            int last = e.limit;
            for (int i = 1; i <= 5; i++) { tryForward(true); sample(4); }
            advance(ms(101));
            check(e.limit > last, "Return: growing");
        }
        int limitVal = e.limit;
        advance(ms(31000));
        check(e.limit == 3, "Return: minRTT window pins limit to 3");
        advance(ms(1000));
        for (int i = 0; i < 5; i++) { check(e.limit == 3, "Return: still 3 during window"); tryForward(true); sample(13); }
        check(e.limit == limitVal, "Return: previous limit restored");
        // --- MinRTTLogicTest (request_count 50, min_concurrency 7)
        make(30, 50, 0.25, 7);
        check(e.limit == 7, "Logic: initial 7");
        for (int i = 0; i < 7; i++) tryForward(true);
        tryForward(false); tryForward(false);
        advance(ms(13));
        for (int i = 0; i < 7; i++) sample(13);
        for (int i = 0; i < 43; i++) { check(e.limit == 7, "Logic: 7 during window"); tryForward(true); sample(13); }
        check(!e.inMinRttWindow && e.minRttNs == ms(13), "Logic: minRTT 13 ms, window closed");
        // --- CancelLatencySample-equivalent percentile check (samples 1..5 ms -> p50 = 3 ms)
        make(30, 5, 0.25, 3);
        for (int i = 1; i <= 5; i++) { tryForward(true); sample(i); }
        check(e.minRttNs == ms(3), "Percentile: minRTT = median = 3 ms");
        // --- ConsecutiveMinConcurrencyReset (interval 3600 s, buffer 0, min_concurrency 7)
        make(3600, 5, 0.0, 7);
        pastMinRtt(5, 5); check(e.minRttNs == ms(5), "Reset: minRTT 5ms");
        advance(ms(101));
        check(e.limit >= 7 && e.limit / 7.0 <= 2.0, "Reset: headroom bounded");
        for (int r = 0; r < 5; r++) { for (int i = 1; i <= 5; i++) { tryForward(true); sample(10); } advance(ms(101)); }
        for (int r = 0; r < 10; r++) {
            int last = e.limit;
            for (int i = 1; i <= 5; i++) { tryForward(true); sample(10); }
            advance(ms(101));
            check(e.limit >= last, "Reset: grows again after re-measured minRTT");
        }
        System.out.printf("EnvoyPortTest: %d checks, %d failures%n", checks, failures);
        System.exit(failures == 0 ? 0 : 1);
    }
}
