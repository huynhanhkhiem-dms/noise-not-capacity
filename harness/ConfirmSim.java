import java.util.*;

/**
 * Finite-horizon robustness simulator for Delta and the static oracle.
 * This class deliberately depends only on Delta.java so the robustness block can be rerun
 * without fetching third-party limiter libraries. The FCFS event model and random service laws
 * match the corresponding paths in Sim.java.
 */
public final class ConfirmSim {
    static long now = 0L;
    interface Ctl { boolean admit(); Object token(); void done(Object tok, long admitNs); int limit(); }
    static final class DeltaCtl implements Ctl {
        final Delta d;
        DeltaCtl(Delta d) { this.d = d; }
        public boolean admit() { return d.admit(); }
        public Object token() { return d.token(); }
        public void done(Object tok, long admitNs) { d.done(tok, now-admitNs); }
        public int limit() { return d.limit(); }
    }
    static final class StaticCtl implements Ctl {
        final int L; int out=0;
        StaticCtl(int L){this.L=L;}
        public boolean admit(){ if(out<L){out++; return true;} return false; }
        public Object token(){return null;}
        public void done(Object tok,long admitNs){out--;}
        public int limit(){return L;}
    }
    static final class Job { Object tok; long admit; double work; long seq; }
    static double gauss(SplittableRandom r){ double u=1-r.nextDouble(), v=r.nextDouble(); return Math.sqrt(-2*Math.log(u))*Math.cos(2*Math.PI*v); }
    static double draw(String dist,double meanNs,SplittableRandom r){
        switch(dist){
            case "det": return meanNs;
            case "exp": return -Math.log(1-r.nextDouble())*meanNs;
            case "ln05": case "ln1": case "ln15": {
                double sg=dist.equals("ln05")?0.5:dist.equals("ln1")?1.0:1.5;
                return Math.exp(Math.log(meanNs)-sg*sg/2+sg*gauss(r)); }
            case "par25": { double a=2.5, xm=meanNs*(a-1)/a; return xm/Math.pow(1-r.nextDouble(),1/a); }
            default: throw new IllegalArgumentException(dist);
        }
    }
    public static void main(String[] a){
        String algo=a[0]; int c=Integer.parseInt(a[1]); double meanMs=Double.parseDouble(a[2]);
        String dist=a[3]; double rho=Double.parseDouble(a[4]); double durS=Double.parseDouble(a[5]); long seed=Long.parseLong(a[6]);
        Map<String,String> kv=new HashMap<>(); for(int i=7;i<a.length;i++){String[]p=a[i].split("=",2);kv.put(p[0],p.length>1?p[1]:"");}
        int maxLimit=1000;
        Ctl ctl;
        if(algo.equals("delta")){
            Delta d=new Delta(Double.parseDouble(kv.getOrDefault("initL","20")),0.1,0.8,0.1,200,1,maxLimit,seed);
            d.nPerL=1; ctl=new DeltaCtl(d);
        } else if(algo.equals("static")) ctl=new StaticCtl(c); else throw new IllegalArgumentException(algo);
        double meanNs=meanMs*1e6;
        SplittableRandom rA=new SplittableRandom(seed), rS=new SplittableRandom(seed*7919+17);
        PriorityQueue<long[]> pq=new PriorityQueue<>((x,y)->x[0]!=y[0]?Long.compare(x[0],y[0]):Long.compare(x[1],y[1]));
        ArrayList<Job> jobs=new ArrayList<>(); ArrayDeque<Integer> freeIds=new ArrayDeque<>(); ArrayDeque<Job> fifo=new ArrayDeque<>();
        long seq=0,endT=(long)(durS*1e9),statStart=endT/2;
        pq.add(new long[]{(long)(-Math.log(1-rA.nextDouble())/(rho*c/meanNs)),seq++,0,-1});
        int busy=0; long arrivals=0,rejected=0,done=0,lastT=0; double sumLat=0,busyArea=0,limitArea=0;
        while(!pq.isEmpty()){
            long[] e=pq.poll(); long t=e[0]; if(t>endT) break; now=t;
            if(t>=statStart){ long from=Math.max(lastT,statStart); busyArea+=busy*(double)(t-from); limitArea+=ctl.limit()*(double)(t-from); }
            lastT=t;
            if(e[2]==0){
                pq.add(new long[]{now+(long)(-Math.log(1-rA.nextDouble())/(rho*c/meanNs)),seq++,0,-1});
                if(now>=statStart) arrivals++;
                if(!ctl.admit()){ if(now>=statStart) rejected++; continue; }
                Job j=new Job(); j.tok=ctl.token(); j.admit=now; j.work=draw(dist,meanNs,rS); j.seq=seq++;
                if(busy<c){busy++; start(j,pq,jobs,freeIds,seq++);} else fifo.add(j);
            } else {
                int id=(int)e[3]; Job j=jobs.get(id); jobs.set(id,null); freeIds.push(id); ctl.done(j.tok,j.admit);
                long rtt=now-j.admit; if(j.admit>=statStart){done++;sumLat+=rtt/1e6;}
                if(!fifo.isEmpty()){Job k=fifo.poll();start(k,pq,jobs,freeIds,seq++);} else busy--;
            }
        }
        double util=busyArea/(c*(double)(endT-statStart)); double meanLimit=limitArea/(endT-statStart);
        String extra=""; if(ctl instanceof DeltaCtl){ Delta d=((DeltaCtl)ctl).d; extra=String.format(Locale.ROOT," nPairs=%d eMean=%.4f",d.nE,d.sumE/Math.max(1,d.nE)); }
        System.out.printf(Locale.ROOT,"RES algo=%s c=%d S=%.1f dist=%s rho=%.2f seed=%d meanLimit=%.2f limitOverC=%.4f util=%.4f reject=%.4f meanLatOverS=%.4f%s%n",
            algo,c,meanMs,dist,rho,seed,meanLimit,meanLimit/c,util,arrivals>0?(double)rejected/arrivals:0.0,done>0?sumLat/done/meanMs:Double.NaN,extra);
    }
    static void start(Job j,PriorityQueue<long[]>pq,ArrayList<Job>jobs,ArrayDeque<Integer>freeIds,long seq){
        int id=freeIds.isEmpty()?jobs.size():freeIds.pop(); if(id==jobs.size())jobs.add(j);else jobs.set(id,j);
        pq.add(new long[]{now+Math.max(1L,(long)j.work),seq,1,id});
    }
}
