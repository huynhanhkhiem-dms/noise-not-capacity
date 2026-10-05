import com.netflix.concurrency.limits.Limit;
import com.netflix.concurrency.limits.Limiter;
import com.netflix.concurrency.limits.limit.*;
import com.netflix.concurrency.limits.limiter.SimpleLimiter;

import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * Discrete-event harness for adaptive concurrency limiters (simulated nanosecond clock, fully reproducible).
 *
 * System: open-loop Poisson arrivals (rate rho * c / meanS) -> admission controller -> server.
 * Server: FCFS with c identical workers (default) or egalitarian processor sharing over c cores (server=ps).
 * The controller observes RTT = completion - admission, exactly as a server-side limiter does in production.
 *
 * Controllers
 *   vegas | vegasW | g2 | g2W | grad | gradW | aimd  : REAL Netflix concurrency-limits classes (commit 78a74b9)
 *   envoy                                            : faithful port of Envoy GradientController (commit b71f63b)
 *   delta                                            : excitation-based limiter proposed in the paper
 *   static (static=L)  | none                        : oracle / no limiter
 *
 * usage: Sim algo c meanMs dist rho durS seed [key=value ...]
 *   dist   : det | exp | ln05 | ln1 | ln15 | par25 | file:<path>   (file: empirical service times, rescaled to meanMs)
 *   keys   : maxLimit=1000 statFrom=0.5 server=fcfs|ps timeout=<ms> ts=<csv path>
 *            envoyWin=100 envoyMinRtt=60000 envoyN=50 envoyPct=0.5
 *            d=0.1 eStar=0.8 gamma=0.1 nMin=200 nPerL=1 initL=20        (delta)
 *            ablations: fixedOrder noSettle noDrain geoMean anyReject    (delta)
 *            change=<t_s>:<field>:<value>[,...]  field in {c, s, rho}     (step changes, s = service-time scale)
 */
public class Sim {
    static long now = 0L;

    interface Ctl {
        boolean admit();
        Object token();
        void done(Object tok, long admitNs, boolean timedOut);
        int limit();
        default long nextTimer() { return Long.MAX_VALUE; }
        default void onTimer() {}
    }

    static final class NetflixCtl implements Ctl {
        final SimpleLimiter<Void> lim; Limiter.Listener last;
        NetflixCtl(Limit l) { lim = SimpleLimiter.newBuilder().limit(l).nanoClock(() -> now).build(); }
        public boolean admit() { Optional<Limiter.Listener> o = lim.acquire(null); if (o.isPresent()) { last = o.get(); return true; } return false; }
        public Object token() { return last; }
        public void done(Object tok, long admitNs, boolean timedOut) { if (timedOut) ((Limiter.Listener) tok).onDropped(); else ((Limiter.Listener) tok).onSuccess(); }
        public int limit() { return lim.getLimit(); }
    }

    static final class EnvoyCtl implements Ctl {
        final Envoy e;
        EnvoyCtl(Envoy e) { this.e = e; e.start(0); }
        public boolean admit() { return e.admit(); }
        public Object token() { return null; }
        public void done(Object tok, long admitNs, boolean timedOut) { e.onDone(admitNs, now); }
        public int limit() { return e.limit; }
        public long nextTimer() { return e.nextTimer(); }
        public void onTimer() { e.onTimers(now); }
    }

    static final class DeltaCtl implements Ctl {
        final Delta d;
        DeltaCtl(Delta d) { this.d = d; }
        public boolean admit() { return d.admit(); }
        public Object token() { return d.token(); }
        public void done(Object tok, long admitNs, boolean timedOut) { d.done(tok, now - admitNs); }
        public int limit() { return d.limit(); }
    }

    static final class StaticCtl implements Ctl {
        final int L; int out = 0;
        StaticCtl(int L) { this.L = L; }
        public boolean admit() { if (out < L) { out++; return true; } return false; }
        public Object token() { return null; }
        public void done(Object tok, long a, boolean t) { out--; }
        public int limit() { return L; }
    }

    static Limit netflixLimit(String algo, int maxLimit, long timeoutNs) {
        switch (algo) {
            case "vegas":  return VegasLimit.newBuilder().maxConcurrency(maxLimit).build();
            case "vegasW": return WindowedLimit.newBuilder().build(VegasLimit.newBuilder().maxConcurrency(maxLimit).build());
            case "g2":     return Gradient2Limit.newBuilder().maxConcurrency(maxLimit).build();
            case "g2W":    return WindowedLimit.newBuilder().build(Gradient2Limit.newBuilder().maxConcurrency(maxLimit).build());
            case "grad":   return GradientLimit.newBuilder().maxConcurrency(maxLimit).build();
            case "gradW":  return WindowedLimit.newBuilder().build(GradientLimit.newBuilder().maxConcurrency(maxLimit).build());
            case "aimd": {
                AIMDLimit.Builder b = AIMDLimit.newBuilder().maxLimit(maxLimit);
                if (timeoutNs > 0) b = b.timeout(timeoutNs, java.util.concurrent.TimeUnit.NANOSECONDS);
                return b.build();
            }
            default: return null;
        }
    }

    // ---------------- service times (mean = meanNs * scale) ----------------
    static double[] emp = null;
    static double draw(String dist, double meanNs, SplittableRandom r) {
        switch (dist) {
            case "det": return meanNs;
            case "exp": return -Math.log(1 - r.nextDouble()) * meanNs;
            case "ln05": case "ln1": case "ln15": {
                double s = dist.equals("ln05") ? 0.5 : dist.equals("ln1") ? 1.0 : 1.5;
                return Math.exp(Math.log(meanNs) - s * s / 2 + s * gauss(r)); }
            case "par25": { double a = 2.5, xm = meanNs * (a - 1) / a; return xm / Math.pow(1 - r.nextDouble(), 1 / a); }
            default: return emp[r.nextInt(emp.length)] * meanNs;
        }
    }
    static double gauss(SplittableRandom r) { double u = 1 - r.nextDouble(), v = r.nextDouble(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); }

    // ---------------- job ----------------
    static final class Job { Object tok; long admit; double work; double finishTag; long seq; }

    /**
     * VegasLimit (probe jitter) and GradientLimit (probe interval) draw from java.util.concurrent.ThreadLocalRandom,
     * which the JDK seeds from the wall clock. To make every run reproducible from its seed without modifying the
     * library, we set the per-thread ThreadLocalRandom state of the simulation thread from the run's seed
     * (via sun.misc.Unsafe; the harness is single-threaded).
     */
    static void seedThreadLocalRandom(long seed) {
        try {
            java.util.concurrent.ThreadLocalRandom.current();              // initialise this thread's generator
            java.lang.reflect.Field uf = sun.misc.Unsafe.class.getDeclaredField("theUnsafe");
            uf.setAccessible(true);
            sun.misc.Unsafe u = (sun.misc.Unsafe) uf.get(null);
            long off = u.objectFieldOffset(Thread.class.getDeclaredField("threadLocalRandomSeed"));
            u.putLong(Thread.currentThread(), off, seed * 0x9E3779B97F4A7C15L + 0x632BE59BD9B4E019L);
        } catch (Exception e) { throw new RuntimeException("cannot seed ThreadLocalRandom", e); }
    }

    public static void main(String[] a) throws IOException {
        String algo = a[0]; int c = Integer.parseInt(a[1]); double meanMs = Double.parseDouble(a[2]);
        String dist = a[3]; double rho = Double.parseDouble(a[4]); double durS = Double.parseDouble(a[5]); long seed = Long.parseLong(a[6]);
        seedThreadLocalRandom(seed);
        Map<String, String> kv = new HashMap<>();
        for (int i = 7; i < a.length; i++) { String[] p = a[i].split("=", 2); kv.put(p[0], p.length > 1 ? p[1] : ""); }
        int maxLimit = Integer.parseInt(kv.getOrDefault("maxLimit", "1000"));
        boolean ps = kv.getOrDefault("server", "fcfs").equals("ps");
        long timeoutNs = (long) (Double.parseDouble(kv.getOrDefault("timeout", "0")) * 1e6);
        String distName = dist;
        if (dist.startsWith("file:")) {
            List<String> lines = Files.readAllLines(Paths.get(dist.substring(5)));
            emp = lines.stream().filter(s -> !s.isBlank() && !s.startsWith("#")).mapToDouble(Double::parseDouble).toArray();
            double m = Arrays.stream(emp).average().orElse(1); for (int i = 0; i < emp.length; i++) emp[i] /= m;
            distName = Paths.get(dist.substring(5)).getFileName().toString().replace(".txt", "");
        }
        // step changes
        double[][] changes = new double[0][];
        String[] changeFields = new String[0];
        if (kv.containsKey("change")) {
            String[] parts = kv.get("change").split(",");
            changes = new double[parts.length][]; changeFields = new String[parts.length];
            for (int i = 0; i < parts.length; i++) { String[] f = parts[i].split(":"); changes[i] = new double[]{Double.parseDouble(f[0]) * 1e9, Double.parseDouble(f[2])}; changeFields[i] = f[1]; }
        }
        final double meanNs0 = meanMs * 1e6;
        double sScale = 1.0; double curRho = rho; int curC = c;
        SplittableRandom rA = new SplittableRandom(seed), rS = new SplittableRandom(seed * 7919 + 17);

        Ctl ctl;
        Limit nl = netflixLimit(algo, maxLimit, timeoutNs);
        if (nl != null) ctl = new NetflixCtl(nl);
        else if (algo.equals("envoy")) ctl = new EnvoyCtl(new Envoy(
                (long) (Double.parseDouble(kv.getOrDefault("envoyWin", "100")) * 1e6),
                (long) (Double.parseDouble(kv.getOrDefault("envoyMinRtt", "60000")) * 1e6),
                maxLimit, Integer.parseInt(kv.getOrDefault("envoyN", "50")),
                Double.parseDouble(kv.getOrDefault("envoyPct", "0.5")), seed));
        else if (algo.equals("delta")) ctl = new DeltaCtl(new Delta(
                Double.parseDouble(kv.getOrDefault("initL", "20")), Double.parseDouble(kv.getOrDefault("d", "0.1")),
                Double.parseDouble(kv.getOrDefault("eStar", "0.8")), Double.parseDouble(kv.getOrDefault("gamma", "0.1")),
                Integer.parseInt(kv.getOrDefault("nMin", "200")), 1, maxLimit, seed));
        else if (algo.equals("static")) ctl = new StaticCtl(Integer.parseInt(kv.get("static")));
        else if (algo.equals("none")) ctl = new StaticCtl(Integer.MAX_VALUE);
        else throw new IllegalArgumentException(algo);
        if (ctl instanceof EnvoyCtl && kv.containsKey("epochlog")) {   // optional Envoy minRTT-window log (diagnostics only)
            Envoy en = ((EnvoyCtl) ctl).e;
            en.epochLog = new PrintWriter(new BufferedWriter(new FileWriter(kv.get("epochlog"))));
            en.epochLog.println("window_start_s,window_end_s,minrtt_ms,restored_limit");
        }
        if (ctl instanceof DeltaCtl) {
            Delta dl = ((DeltaCtl) ctl).d;
            dl.nPerL = Double.parseDouble(kv.getOrDefault("nPerL", "1"));
            dl.fixedOrder = kv.containsKey("fixedOrder"); dl.noSettle = kv.containsKey("noSettle");
            dl.noDrain = kv.containsKey("noDrain"); dl.geoMean = kv.containsKey("geoMean");
            dl.anyReject = kv.containsKey("anyReject");
        }

        PrintWriter ts = kv.containsKey("ts") ? new PrintWriter(new BufferedWriter(new FileWriter(kv.get("ts")))) : null;
        if (ts != null) ts.println("t_s,limit,inflight,busy,completions,mean_rtt_ms,rejections,arrivals,c,s_scale");

        // event queue: {time, seq, type(0=arrival,1=fcfs completion), jobIndex}
        PriorityQueue<long[]> pq = new PriorityQueue<>((x, y) -> x[0] != y[0] ? Long.compare(x[0], y[0]) : Long.compare(x[1], y[1]));
        ArrayList<Job> jobs = new ArrayList<>(); ArrayDeque<Integer> freeIds = new ArrayDeque<>();
        ArrayDeque<Job> fifo = new ArrayDeque<>();
        // processor sharing state: virtual time V advances at rate min(1, c/n) per job
        PriorityQueue<Job> psHeap = new PriorityQueue<>((x, y) -> x.finishTag != y.finishTag ? Double.compare(x.finishTag, y.finishTag) : Long.compare(x.seq, y.seq));
        double V = 0; long lastPsT = 0;

        long seq = 0; int busy = 0;
        long endT = (long) (durS * 1e9), statStart = (long) (endT * Double.parseDouble(kv.getOrDefault("statFrom", "0.5")));
        pq.add(new long[]{(long) (-Math.log(1 - rA.nextDouble()) / (curRho * curC / (meanNs0 * sScale))), seq++, 0, -1});
        int nextChange = 0;

        long arrivals = 0, rejected = 0, done = 0, timeouts = 0; double sumLat = 0, limitArea = 0; long lastT = 0;
        double[] lat = new double[4_000_000]; int nLat = 0;
        long nextTs = 1_000_000_000L; long tsComp = 0, tsRej = 0, tsArr = 0; double tsLat = 0;
        double busyArea = 0; // for utilisation with time-varying c
        double capArea = 0;

        while (true) {
            long tArr = pq.isEmpty() ? Long.MAX_VALUE : pq.peek()[0];
            long tPs = Long.MAX_VALUE;
            if (ps && !psHeap.isEmpty()) {
                int n = psHeap.size(); double rate = Math.min(1.0, (double) curC / n);
                tPs = lastPsT + (long) Math.ceil((psHeap.peek().finishTag - V) / rate);
            }
            long tTimer = ctl.nextTimer();
            long tChange = nextChange < changes.length ? (long) changes[nextChange][0] : Long.MAX_VALUE;
            long t = Math.min(Math.min(tArr, tPs), Math.min(tTimer, tChange));
            if (t > endT) break;
            // accounting
            if (t >= statStart) {
                long from = Math.max(lastT, statStart);
                limitArea += ctl.limit() * (double) (t - from);
                busyArea += (ps ? Math.min(curC, psHeap.size()) : busy) * (double) (t - from);
                capArea += curC * (double) (t - from);
            }
            if (ps) { int n = psHeap.size(); if (n > 0) V += (t - lastPsT) * Math.min(1.0, (double) curC / n); lastPsT = t; }
            lastT = t; now = t;
            while (ts != null && now >= nextTs) {
                ts.printf(Locale.ROOT, "%.0f,%d,%d,%d,%d,%.4f,%d,%d,%d,%.3f%n", nextTs / 1e9, ctl.limit(), ps ? psHeap.size() : busy + fifo.size(),
                        ps ? Math.min(curC, psHeap.size()) : busy, tsComp, tsComp > 0 ? tsLat / tsComp : Double.NaN, tsRej, tsArr, curC, sScale);
                tsComp = 0; tsRej = 0; tsArr = 0; tsLat = 0; nextTs += 1_000_000_000L;
            }
            if (t == tChange) {
                String f = changeFields[nextChange]; double v = changes[nextChange][1]; nextChange++;
                if (f.equals("c")) {
                    int newC = (int) v;
                    if (!ps) { // add workers: start queued jobs; remove workers: they finish current job and stop
                        curC = newC;
                        while (busy < curC && !fifo.isEmpty()) { Job k = fifo.poll(); busy++; startFcfs(k, pq, jobs, freeIds, seq++); }
                    } else curC = newC;
                } else if (f.equals("s")) sScale = v;
                else if (f.equals("rho")) curRho = v;
                continue;
            }
            if (t == tTimer && tTimer <= tArr && tTimer <= tPs) { ctl.onTimer(); continue; }
            if (t == tPs && tPs <= tArr) { // PS completion
                Job j = psHeap.poll();
                complete(j, ctl, timeoutNs, statStart);
                long rtt = now - j.admit; boolean to = timeoutNs > 0 && rtt > timeoutNs;
                if (to) timeouts++;
                tsComp++; tsLat += rtt / 1e6;
                if (j.admit >= statStart) { done++; double l = rtt / 1e6; sumLat += l; if (nLat < lat.length) lat[nLat++] = l; }
                continue;
            }
            long[] e = pq.poll();
            if (e[2] == 0) { // arrival
                double lam = curRho * c / (meanNs0);   // offered load relative to the INITIAL capacity and service time
                pq.add(new long[]{now + (long) (-Math.log(1 - rA.nextDouble()) / lam), seq++, 0, -1});
                boolean in = now >= statStart; if (in) arrivals++; tsArr++;
                if (!ctl.admit()) { if (in) rejected++; tsRej++; continue; }
                Job j = new Job(); j.tok = ctl.token(); j.admit = now; j.work = draw(dist, meanNs0 * sScale, rS); j.seq = seq++;
                if (ps) { j.finishTag = V + j.work; psHeap.add(j); }
                else if (busy < curC) { busy++; startFcfs(j, pq, jobs, freeIds, seq++); }
                else fifo.add(j);
            } else { // FCFS completion
                int id = (int) e[3]; Job j = jobs.get(id); jobs.set(id, null); freeIds.push(id);
                complete(j, ctl, timeoutNs, statStart);
                long rtt = now - j.admit; if (timeoutNs > 0 && rtt > timeoutNs) timeouts++;
                tsComp++; tsLat += rtt / 1e6;
                if (j.admit >= statStart) { done++; double l = rtt / 1e6; sumLat += l; if (nLat < lat.length) lat[nLat++] = l; }
                if (busy > curC) { busy--; } // a removed worker retires
                else if (!fifo.isEmpty()) { Job k = fifo.poll(); startFcfs(k, pq, jobs, freeIds, seq++); }
                else busy--;
            }
        }
        if (ts != null) ts.close();
        if (ctl instanceof EnvoyCtl && ((EnvoyCtl) ctl).e.epochLog != null) ((EnvoyCtl) ctl).e.epochLog.close();
        double statDur = (endT - statStart) / 1e9;
        Arrays.sort(lat, 0, nLat);
        double p50 = nLat > 0 ? lat[nLat / 2] : Double.NaN, p99 = nLat > 0 ? lat[(int) (nLat * 0.99)] : Double.NaN;
        double util = busyArea / capArea;
        double meanLimit = limitArea / (endT - statStart);
        String extra = "";
        if (ctl instanceof DeltaCtl) { Delta dd = ((DeltaCtl) ctl).d; extra = String.format(Locale.ROOT, " eMean=%.4f eSd=%.4f nPairs=%d cvR=%.4f", dd.sumE / Math.max(1, dd.nE), Math.sqrt(Math.max(0, dd.sumE2 / Math.max(1, dd.nE) - Math.pow(dd.sumE / Math.max(1, dd.nE), 2))), dd.nE, dd.sumCv / Math.max(1, dd.nCv)); }
        System.out.printf(Locale.ROOT,
            "RES algo=%s c=%d S=%.1f dist=%s rho=%.2f seed=%d server=%s meanLimit=%.2f limitOverC=%.4f util=%.4f reject=%.4f excessReject=%.4f meanLatOverS=%.4f p50OverS=%.4f p99OverS=%.4f timeouts=%d%s%n",
            algo, c, meanMs, distName, rho, seed, ps ? "ps" : "fcfs", meanLimit, meanLimit / c, util,
            arrivals > 0 ? (double) rejected / arrivals : 0.0,
            arrivals > 0 ? (double) rejected / arrivals - Math.max(0, 1 - 1 / rho) : 0.0,
            done > 0 ? sumLat / done / meanMs : Double.NaN, p50 / meanMs, p99 / meanMs, timeouts, extra);
    }

    static void startFcfs(Job j, PriorityQueue<long[]> pq, ArrayList<Job> jobs, ArrayDeque<Integer> freeIds, long seq) {
        int id = freeIds.isEmpty() ? jobs.size() : freeIds.pop();
        if (id == jobs.size()) jobs.add(j); else jobs.set(id, j);
        pq.add(new long[]{now + Math.max(1L, (long) j.work), seq, 1, id});
    }

    static void complete(Job j, Ctl ctl, long timeoutNs, long statStart) {
        long rtt = now - j.admit;
        ctl.done(j.tok, j.admit, timeoutNs > 0 && rtt > timeoutNs);
    }
}
