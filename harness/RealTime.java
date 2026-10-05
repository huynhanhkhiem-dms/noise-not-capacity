import com.netflix.concurrency.limits.Limit;
import com.netflix.concurrency.limits.Limiter;
import com.netflix.concurrency.limits.limit.*;
import com.netflix.concurrency.limits.limiter.SimpleLimiter;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.concurrent.locks.LockSupport;

/**
 * Wall-clock validation: the same experiment as Sim, but with real threads and the real clock.
 *   server  : ThreadPoolExecutor with c worker threads and an unbounded FIFO queue; a request "works"
 *             by sleeping for a service time drawn from the chosen law (I/O-bound service emulation)
 *   load    : one generator thread producing Poisson arrivals (LockSupport.parkNanos)
 *   limiter : Netflix SimpleLimiter (System.nanoTime) with VegasLimit (library default) or
 *             WindowedLimit(Gradient2Limit) (README), or Delta (synchronized wrapper)
 * usage: RealTime algo c meanMs dist rho durS seed
 */
public class RealTime {
    public static void main(String[] a) throws Exception {
        String algo = a[0]; int c = Integer.parseInt(a[1]); double meanMs = Double.parseDouble(a[2]);
        String dist = a[3]; double rho = Double.parseDouble(a[4]); double durS = Double.parseDouble(a[5]); long seed = Long.parseLong(a[6]);
        double meanNs = meanMs * 1e6, lambda = rho * c / meanNs;
        SplittableRandom rS = new SplittableRandom(seed * 7919 + 17), rA = new SplittableRandom(seed);
        ThreadPoolExecutor pool = new ThreadPoolExecutor(c, c, 60, TimeUnit.SECONDS, new LinkedBlockingQueue<>());
        pool.prestartAllCoreThreads();
        AtomicInteger busy = new AtomicInteger();
        AtomicLong done = new AtomicLong(), rejected = new AtomicLong(), arrivals = new AtomicLong();
        DoubleAdder latSum = new DoubleAdder();
        final long t0 = System.nanoTime(), statStart = t0 + (long) (durS * 0.5 * 1e9), end = t0 + (long) (durS * 1e9);

        final SimpleLimiter<Void> nf;
        final Delta dl;
        if (algo.equals("delta")) { nf = null; dl = new Delta(20, 0.1, 0.8, 0.1, 200, 1, 1000, seed); dl.nPerL = 1; }
        else {
            Limit lim = algo.equals("vegas") ? VegasLimit.newBuilder().maxConcurrency(1000).build()
                    : WindowedLimit.newBuilder().build(Gradient2Limit.newBuilder().maxConcurrency(1000).build());
            nf = SimpleLimiter.newBuilder().limit(lim).build(); dl = null;
        }
        // sampler thread: time-averaged limit and busy workers over the second half
        double[] acc = new double[3];
        Thread sampler = new Thread(() -> {
            while (System.nanoTime() < end) {
                LockSupport.parkNanos(10_000_000L);
                if (System.nanoTime() >= statStart) {
                    int L; synchronized (RealTime.class) { L = nf != null ? nf.getLimit() : dl.limit(); }
                    acc[0] += L; acc[1] += busy.get(); acc[2] += 1;
                }
            }
        });
        sampler.start();
        long next = t0;
        while (true) {
            next += (long) (-Math.log(1 - rA.nextDouble()) / lambda);
            long now = System.nanoTime();
            if (next > end) break;
            if (next > now) LockSupport.parkNanos(next - now);
            final long adm = System.nanoTime();
            final boolean inStat = adm >= statStart;
            if (inStat) arrivals.incrementAndGet();
            final Object tok; final Limiter.Listener lis;
            if (nf != null) {
                Optional<Limiter.Listener> o = nf.acquire(null);
                if (!o.isPresent()) { if (inStat) rejected.incrementAndGet(); continue; }
                lis = o.get(); tok = null;
            } else {
                synchronized (RealTime.class) {
                    if (!dl.admit()) { if (inStat) rejected.incrementAndGet(); continue; }
                    tok = dl.token();
                }
                lis = null;
            }
            final long svc = (long) Sim.draw(dist, meanNs, rS);
            pool.execute(() -> {
                busy.incrementAndGet();
                try { Thread.sleep(svc / 1_000_000L, (int) (svc % 1_000_000L)); } catch (InterruptedException ie) { }
                busy.decrementAndGet();
                long fin = System.nanoTime();
                if (lis != null) lis.onSuccess();
                else synchronized (RealTime.class) { dl.done(tok, fin - adm); }
                if (adm >= statStart) { done.incrementAndGet(); latSum.add((fin - adm) / 1e6); }
            });
        }
        sampler.join();
        pool.shutdown(); pool.awaitTermination(120, TimeUnit.SECONDS);
        double statDur = durS * 0.5, capacity = c / (meanNs / 1e9);
        System.out.printf(Locale.ROOT,
            "RES algo=%s-rt c=%d S=%.1f dist=%s rho=%.2f seed=%d meanLimit=%.2f limitOverC=%.4f util=%.4f reject=%.4f excessReject=%.4f meanLatOverS=%.4f throughputUtil=%.4f%n",
            algo, c, meanMs, dist, rho, seed, acc[0] / acc[2], acc[0] / acc[2] / c, acc[1] / acc[2] / c,
            (double) rejected.get() / arrivals.get(), (double) rejected.get() / arrivals.get() - Math.max(0, 1 - 1 / rho),
            latSum.sum() / done.get() / meanMs, done.get() / statDur / capacity);
    }
}
