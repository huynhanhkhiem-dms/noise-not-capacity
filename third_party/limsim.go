// limsim drives the REAL failsafe-go AdaptiveLimiter (commit 5759a5e, clock patched to simulated time;
// see failsafe_simclock.patch) with the same open-loop Poisson / FCFS-or-PS c-server model as
// harness/Sim.java. Arguments mirror Sim.java:
//
//	limsim c meanMs dist rho durS seed [key=value ...]
//	keys: maxLimit=1000 statFrom=0.5 server=fcfs|ps ts=<csv> change=<t_s>:<c|s|rho>:<v>[,...]
//	dist: det|exp|ln05|ln1|ln15|par25|file:<path>
package main

import (
	"bufio"
	"container/heap"
	"fmt"
	"math"
	"math/rand"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/failsafe-go/failsafe-go/adaptivelimiter"
	"github.com/failsafe-go/failsafe-go/internal/util"
)

var simNow int64
var epoch = time.Unix(1_700_000_000, 0)

type job struct {
	p      adaptivelimiter.Permit
	admit  int64
	work   float64
	finish float64
	seq    int64
	idx    int
}

type ev struct {
	t    int64
	seq  int64
	kind int
	j    *job
}
type evq []*ev

func (q evq) Len() int { return len(q) }
func (q evq) Less(i, k int) bool {
	if q[i].t != q[k].t {
		return q[i].t < q[k].t
	}
	return q[i].seq < q[k].seq
}
func (q evq) Swap(i, k int)       { q[i], q[k] = q[k], q[i] }
func (q *evq) Push(x interface{}) { *q = append(*q, x.(*ev)) }
func (q *evq) Pop() interface{}   { o := *q; n := len(o); x := o[n-1]; *q = o[:n-1]; return x }

type psq []*job

func (q psq) Len() int { return len(q) }
func (q psq) Less(i, k int) bool {
	if q[i].finish != q[k].finish {
		return q[i].finish < q[k].finish
	}
	return q[i].seq < q[k].seq
}
func (q psq) Swap(i, k int)       { q[i], q[k] = q[k], q[i] }
func (q *psq) Push(x interface{}) { *q = append(*q, x.(*job)) }
func (q *psq) Pop() interface{}   { o := *q; n := len(o); x := o[n-1]; *q = o[:n-1]; return x }

var emp []float64

func draw(dist string, mean float64, r *rand.Rand) float64 {
	switch dist {
	case "det":
		return mean
	case "exp":
		return r.ExpFloat64() * mean
	case "ln05", "ln1", "ln15":
		s := map[string]float64{"ln05": 0.5, "ln1": 1.0, "ln15": 1.5}[dist]
		return math.Exp(math.Log(mean) - s*s/2 + s*r.NormFloat64())
	case "par25":
		a := 2.5
		xm := mean * (a - 1) / a
		return xm / math.Pow(1-r.Float64(), 1/a)
	default:
		return emp[r.Intn(len(emp))] * mean
	}
}

func main() {
	c, _ := strconv.Atoi(os.Args[1])
	meanMs, _ := strconv.ParseFloat(os.Args[2], 64)
	dist := os.Args[3]
	rho, _ := strconv.ParseFloat(os.Args[4], 64)
	durS, _ := strconv.ParseFloat(os.Args[5], 64)
	seed, _ := strconv.ParseInt(os.Args[6], 10, 64)
	kv := map[string]string{}
	for _, a := range os.Args[7:] {
		p := strings.SplitN(a, "=", 2)
		if len(p) == 2 {
			kv[p[0]] = p[1]
		} else {
			kv[p[0]] = ""
		}
	}
	get := func(k, d string) string {
		if v, ok := kv[k]; ok {
			return v
		}
		return d
	}
	maxLimit, _ := strconv.Atoi(get("maxLimit", "1000"))
	statFrom, _ := strconv.ParseFloat(get("statFrom", "0.5"), 64)
	ps := get("server", "fcfs") == "ps"
	distName := dist
	if strings.HasPrefix(dist, "file:") {
		f, err := os.Open(dist[5:])
		if err != nil {
			panic(err)
		}
		sc := bufio.NewScanner(f)
		sum := 0.0
		for sc.Scan() {
			s := strings.TrimSpace(sc.Text())
			if s == "" || strings.HasPrefix(s, "#") {
				continue
			}
			v, _ := strconv.ParseFloat(s, 64)
			emp = append(emp, v)
			sum += v
		}
		f.Close()
		m := sum / float64(len(emp))
		for i := range emp {
			emp[i] /= m
		}
		distName = strings.TrimSuffix(filepath.Base(dist[5:]), ".txt")
	}
	type change struct {
		t     int64
		field string
		v     float64
	}
	var changes []change
	if s, ok := kv["change"]; ok {
		for _, part := range strings.Split(s, ",") {
			f := strings.Split(part, ":")
			ts, _ := strconv.ParseFloat(f[0], 64)
			v, _ := strconv.ParseFloat(f[2], 64)
			changes = append(changes, change{int64(ts * 1e9), f[1], v})
		}
	}
	util.SimNow = func() time.Time { return epoch.Add(time.Duration(simNow)) }
	lim := adaptivelimiter.NewBuilder[any]().WithLimits(1, uint(maxLimit), 20).Build()

	meanNs0 := meanMs * 1e6
	sScale, curRho, curC := 1.0, rho, c
	rA := rand.New(rand.NewSource(seed))
	rS := rand.New(rand.NewSource(seed*7919 + 17))
	var tsw *bufio.Writer
	if p, ok := kv["ts"]; ok {
		f, _ := os.Create(p)
		defer f.Close()
		tsw = bufio.NewWriter(f)
		defer tsw.Flush()
		fmt.Fprintln(tsw, "t_s,limit,inflight,busy,completions,mean_rtt_ms,rejections,arrivals,c,s_scale")
	}
	q := &evq{}
	pq := &psq{}
	V, lastPsT := 0.0, int64(0)
	var seq int64
	lam := func() float64 { return curRho * float64(c) / meanNs0 }
	heap.Push(q, &ev{t: int64(rA.ExpFloat64() / lam()), seq: seq, kind: 0})
	seq++
	endT := int64(durS * 1e9)
	statStart := int64(float64(endT) * statFrom)
	busy := 0
	fifo := []*job{}
	var arrivals, rejected, done int64
	var sumLat, limitArea, busyArea, capArea float64
	var lastT int64
	lats := make([]float64, 0, 1<<21)
	nextTs := int64(1e9)
	var tsComp, tsRej, tsArr int64
	tsLat := 0.0
	nextChange := 0
	startFcfs := func(j *job) {
		w := int64(j.work)
		if w < 1 {
			w = 1
		}
		heap.Push(q, &ev{t: simNow + w, seq: seq, kind: 1, j: j})
		seq++
	}
	record := func(j *job) {
		rtt := simNow - j.admit
		tsComp++
		tsLat += float64(rtt) / 1e6
		if j.admit >= statStart {
			done++
			l := float64(rtt) / 1e6
			sumLat += l
			if len(lats) < cap(lats) {
				lats = append(lats, l)
			}
		}
	}
	for {
		tArr := int64(math.MaxInt64)
		if q.Len() > 0 {
			tArr = (*q)[0].t
		}
		tPs := int64(math.MaxInt64)
		if ps && pq.Len() > 0 {
			n := pq.Len()
			rate := math.Min(1, float64(curC)/float64(n))
			tPs = lastPsT + int64(math.Ceil(((*pq)[0].finish-V)/rate))
		}
		tCh := int64(math.MaxInt64)
		if nextChange < len(changes) {
			tCh = changes[nextChange].t
		}
		t := tArr
		if tPs < t {
			t = tPs
		}
		if tCh < t {
			t = tCh
		}
		if t > endT {
			break
		}
		if t >= statStart {
			from := lastT
			if from < statStart {
				from = statStart
			}
			limitArea += float64(lim.Limit()) * float64(t-from)
			b := busy
			if ps {
				b = pq.Len()
				if b > curC {
					b = curC
				}
			}
			busyArea += float64(b) * float64(t-from)
			capArea += float64(curC) * float64(t-from)
		}
		if ps {
			if n := pq.Len(); n > 0 {
				V += float64(t-lastPsT) * math.Min(1, float64(curC)/float64(n))
			}
			lastPsT = t
		}
		lastT = t
		simNow = t
		for tsw != nil && simNow >= nextTs {
			inflight := busy + len(fifo)
			b := busy
			if ps {
				inflight = pq.Len()
				b = inflight
				if b > curC {
					b = curC
				}
			}
			ml := math.NaN()
			if tsComp > 0 {
				ml = tsLat / float64(tsComp)
			}
			fmt.Fprintf(tsw, "%d,%d,%d,%d,%d,%.4f,%d,%d,%d,%.3f\n", nextTs/1e9, lim.Limit(), inflight, b, tsComp, ml, tsRej, tsArr, curC, sScale)
			tsComp, tsRej, tsArr, tsLat = 0, 0, 0, 0
			nextTs += 1e9
		}
		if t == tCh {
			ch := changes[nextChange]
			nextChange++
			switch ch.field {
			case "c":
				curC = int(ch.v)
				if !ps {
					for busy < curC && len(fifo) > 0 {
						k := fifo[0]
						fifo = fifo[1:]
						busy++
						startFcfs(k)
					}
				}
			case "s":
				sScale = ch.v
			case "rho":
				curRho = ch.v
			}
			continue
		}
		if t == tPs && tPs <= tArr {
			j := heap.Pop(pq).(*job)
			j.p.Record()
			record(j)
			continue
		}
		e := heap.Pop(q).(*ev)
		if e.kind == 0 {
			heap.Push(q, &ev{t: simNow + int64(rA.ExpFloat64()/lam()), seq: seq, kind: 0})
			seq++
			in := simNow >= statStart
			if in {
				arrivals++
			}
			tsArr++
			p, ok := lim.TryAcquirePermit()
			if !ok {
				if in {
					rejected++
				}
				tsRej++
				continue
			}
			j := &job{p: p, admit: simNow, work: draw(dist, meanNs0*sScale, rS), seq: seq}
			seq++
			if ps {
				j.finish = V + j.work
				heap.Push(pq, j)
			} else if busy < curC {
				busy++
				startFcfs(j)
			} else {
				fifo = append(fifo, j)
			}
		} else {
			j := e.j
			j.p.Record()
			record(j)
			if busy > curC {
				busy--
			} else if len(fifo) > 0 {
				k := fifo[0]
				fifo = fifo[1:]
				startFcfs(k)
			} else {
				busy--
			}
		}
	}
	statDur := float64(endT-statStart) / 1e9
	sort.Float64s(lats)
	p50, p99 := math.NaN(), math.NaN()
	if len(lats) > 0 {
		p50 = lats[len(lats)/2]
		p99 = lats[int(float64(len(lats))*0.99)]
	}
	_ = statDur
	meanLimit := limitArea / float64(endT-statStart)
	rej := 0.0
	if arrivals > 0 {
		rej = float64(rejected) / float64(arrivals)
	}
	server := "fcfs"
	if ps {
		server = "ps"
	}
	fmt.Printf("RES algo=failsafe c=%d S=%.1f dist=%s rho=%.2f seed=%d server=%s meanLimit=%.2f limitOverC=%.4f util=%.4f reject=%.4f excessReject=%.4f meanLatOverS=%.4f p50OverS=%.4f p99OverS=%.4f timeouts=0\n",
		c, meanMs, distName, rho, seed, server, meanLimit, meanLimit/float64(c), busyArea/capArea, rej,
		rej-math.Max(0, 1-1/rho), sumLat/float64(done)/meanMs, p50/meanMs, p99/meanMs)
}
