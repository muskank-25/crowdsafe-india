"""CrowdSafe India - crowd forecasting and gate-control engine (no web code here).

A "site" is one crowded place (e.g. Haridwar, Kolkata Durga Puja). Each site has venues (pandals, temples, ghats, stations,
markets), dispersal exits, its own crowd pattern and its own road network. Everything is a SIMULATION with ASSUMED numbers
until real counts are sent in (see Site.telemetry).
"""
import json, math, os, random, re, threading, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET, zlib
import networkx as nx
from places import CATALOG

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data"); os.makedirs(DATA, exist_ok=True)

# ---------------- CONFIG (assumptions - tune with local police / event data) ----------------
SIM_SPEED = float(os.environ.get("CROWDSAFE_SPEED", 30))   # default: 1 real second = 30 simulated seconds (1 = real time, 120 = fast demo)
SAFE, WARN, CRIT = 2.0, 3.0, 4.0      # persons per m2: comfortable / crowded / dangerous
METER_AT, CLOSE_AT = 2.8, 3.5         # controller: one-in-one-out / stop entry
UNMETER_AT, REOPEN_AT = 2.2, 2.5      # hysteresis so gates do not flicker
GATE_FLOW = 60                        # persons per minute per metre of gate width
DIVERT_SHARE, DIVERT_MAX_KM = 0.30, 2.5
WALK_KMH, ROAD_FACTOR, N_OFFICERS = 4.5, 1.3, 120
HWY_ALL = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|service|living_street|pedestrian|road"
HWY_MAIN = "motorway|trunk|primary|secondary|tertiary"          # used for large areas to keep downloads small
MIRRORS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
NOISE_SIGMA, SURGE_P, SURGE_FRAC = .15, .004, .30      # forecast uncertainty: arrival noise, chance/size of a sudden rush (assumed)
CONGESTION = .15                                        # crowded venues empty more slowly: dwell grows 15% per person/m2 above SAFE
OFFLINE = os.environ.get("PANDALSAFE_OFFLINE") == "1"            # skip the road download (straight-line fallback)

def hav_km(a, b):
    p1, p2, dl = math.radians(a[0]), math.radians(b[0]), math.radians(b[1] - a[1])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))

def density(p): return p["count"] / p["area"]
def cap(p): return p["area"] * SAFE
def level(d): return "critical" if d >= CRIT else "crowded" if d >= WARN else "busy" if d >= SAFE else "calm"
def _bump(h, c, w): return math.exp(-min((h - c) ** 2, (h - c + 24) ** 2, (h - c - 24) ** 2) / w)

# ---------------- voice / alert messages (English, Hindi, Bengali) ----------------
VOICE = {
 "en": dict(critical="Danger. {n} is critically crowded. Stop entry and open the exit routes.", reminder="Danger continues at {n}. Keep entry stopped and clear the exits.",
            crowded="Warning. {n} is getting crowded.", closed="Entry closed at {n}.", closed_to="Entry closed at {n}. Send people towards {x}.",
            metered="One in, one out at {n}.", alert="Alert at {n}: {x}.", jump="Warning. Sudden jump in the crowd at {n}. Please check.", recovered="{n} is back to a safe level."),
 "hi": dict(critical="खतरा। {n} में बहुत ज़्यादा भीड़ है। प्रवेश रोकें और निकास के रास्ते खोलें।", reminder="{n} में खतरा बना हुआ है। प्रवेश बंद रखें और निकास साफ़ करें।",
            crowded="चेतावनी। {n} में भीड़ बढ़ रही है।", closed="{n} पर प्रवेश बंद किया गया।", closed_to="{n} पर प्रवेश बंद किया गया। लोगों को {x} की ओर भेजें।",
            metered="{n} पर एक-एक करके प्रवेश दें।", alert="{n} पर अलर्ट: {x}।", jump="चेतावनी। {n} में अचानक भीड़ बढ़ी है। कृपया जाँच करें।", recovered="{n} में भीड़ सामान्य हो गई है।"),
 "bn": dict(critical="বিপদ। {n}-এ অতিরিক্ত ভিড়। প্রবেশ বন্ধ করুন এবং বেরোনোর পথ খুলুন।", reminder="{n}-এ বিপদ চলছে। প্রবেশ বন্ধ রাখুন এবং বেরোনোর পথ পরিষ্কার করুন।",
            crowded="সতর্কতা। {n}-এ ভিড় বাড়ছে।", closed="{n}-এ প্রবেশ বন্ধ করা হয়েছে।", closed_to="{n}-এ প্রবেশ বন্ধ করা হয়েছে। লোকজনকে {x}-এর দিকে পাঠান।",
            metered="{n}-এ একজন বেরোলে একজন ঢুকবেন।", alert="{n}-এ সতর্কবার্তা: {x}।", jump="সতর্কতা। {n}-এ হঠাৎ ভিড় বেড়েছে। দেখে নিন।", recovered="{n}-এ ভিড় স্বাভাবিক হয়েছে।")}
ALERT_WORDS = {"hi": {"crush risk": "भगदड़ का खतरा", "blocked exit": "निकास बंद", "panic": "घबराहट", "medical emergency": "चिकित्सा आपातकाल"},
               "bn": {"crush risk": "পদদলিত হওয়ার ঝুঁকি", "blocked exit": "বেরোনোর পথ বন্ধ", "panic": "আতঙ্ক", "medical emergency": "চিকিৎসা জরুরি অবস্থা"}}
LEVEL_RANK = {"calm": 0, "busy": 1, "crowded": 2, "critical": 3}

def render_event(e, lang="en"):
    t = VOICE.get(lang, VOICE["en"]); code = e["code"]; x = e["x"]
    key = "closed_to" if code == "closed" and x else code
    if code == "alert": x = ALERT_WORDS.get(lang, {}).get(x, x)
    return t[key].format(n=e["name"], x=x)

def read_kml(path):
    out = []
    for pm in ET.parse(path).getroot().iter():
        if not pm.tag.endswith("Placemark"): continue
        pt = next((e for e in pm.iter() if e.tag.endswith("Point")), None)
        if pt is None: continue
        g = lambda t: next((c.text for c in pm if c.tag.endswith(t)), "") or ""
        lon, lat = (float(v) for v in next(e.text for e in pt.iter() if e.tag.endswith("coordinates")).strip().split(",")[:2])
        attrs = {k: float(v) for k, v in re.findall(r"(\w+)\s*=\s*([\d.]+)", g("description"))}
        out.append({**attrs, "name": g("name").strip() or "?", "kind": "venue", "lat": lat, "lon": lon})
    return out

def gate_for(p, d=None):
    d = density(p) + (.7 if p["flagged"] else 0) if d is None else d
    g = p["gate"]
    if d >= CLOSE_AT or (g == "CLOSED" and d >= REOPEN_AT): return "CLOSED"
    if d >= METER_AT or (g != "OPEN" and d >= UNMETER_AT): return "METERED"
    return "OPEN"

def best_alt(p, by, neigh):
    c = [by[i] for i in neigh[p["id"]] if density(by[i]) < WARN and by[i]["gate"] == "OPEN"]
    return min(c, key=density) if c else None

def step(p, dt, hm, dm, nxt, by, neigh, mult=1.0):
    """One time step (dt minutes): arrivals -> gate -> inside -> exits; a waiting crowd may be diverted or give up.
    p["pop_adj"] is learned from real counts; mult is random noise used by the Monte Carlo forecast."""
    arr = cap(p) / p["dwell"] * p["pop"] * p["pop_adj"] * hm * dm * .9 * dt * mult + p["extra"]; p["extra"] = 0.0
    pool = arr + p["queue"]
    out = p["count"] / (p["dwell"] * (1 + CONGESTION * max(0.0, density(p) - SAFE))) * dt    # congestion slows exits
    enter = min(pool, p["gate_w"] * GATE_FLOW * dt) if p["gate"] == "OPEN" else min(pool, out) if p["gate"] == "METERED" else 0.0
    q = pool - enter
    if p["gate"] != "OPEN" and q > 0:
        alt = best_alt(p, by, neigh)
        if alt: d = q * DIVERT_SHARE * min(1, dt / 5); nxt[alt["id"]] += d; q -= d
    q -= q * min(1, .02 * dt)                                    # people give up waiting
    p["count"] = max(0.0, p["count"] + enter - out); p["queue"] = max(0.0, q)
    p["arr_min"] = .8 * p["arr_min"] + .2 * arr / dt

class Site:
    def __init__(self, key):
        c = CATALOG[key]
        self.key, self.title, self.note = key, c["title"], c.get("note", "")
        self.peaks, self.base, self.days = c["peaks"], c.get("base", .12), c["days"]
        self.start_hour = c.get("start", 16.0)
        self.start_day = c["day"] if c.get("day") in c["days"] else next(iter(c["days"]))
        self.lock = threading.RLock(); self.seq = 0; self.EVENTS = []
        kml = os.path.join(DATA, key + ".kml")
        if os.path.exists(kml):
            pts = read_kml(kml); is_exit = lambda p: re.search(r"exit|metro|station|ground|hospital", p["name"], re.I)
            self.places, self.exits, self.source = [p for p in pts if not is_exit(p)], [p for p in pts if is_exit(p)], f"data/{key}.kml"
        else:
            self.places, self.exits = [dict(v) for v in c["venues"]], [dict(e) for e in c["exits"]]
            self.source = "built-in SAMPLE (approximate locations, assumed sizes)"
        self.G, self.xy, self.SP, self.routing = None, {}, {}, "straight-line fallback (road data not loaded)"
        self._init_roads()
        for x in self.exits: x["node"] = self.snap(x["lat"], x["lon"])
        self.reset()

    # ---------- roads ----------
    def _fetch_roads(self, s, w, n, e, hwy):
        q = f'[out:json][timeout:120];way["highway"~"^({hwy})$"]({s},{w},{n},{e});(._;>;);out body;'
        for url in MIRRORS:
            try:
                print(f"[{self.key}] downloading roads from", url)
                req = urllib.request.Request(url, data=urllib.parse.urlencode({"data": q}).encode(), headers={"User-Agent": "CrowdSafeIndia/1.0"})
                return json.load(urllib.request.urlopen(req, timeout=180))
            except Exception as ex: print("  failed:", ex)

    def _build_graph(self, data):
        nodes = {e["id"]: (e["lat"], e["lon"]) for e in data["elements"] if e["type"] == "node"}
        g = nx.DiGraph()
        for e in data["elements"]:
            if e["type"] != "way": continue
            t = e.get("tags", {}); one = t.get("oneway") in ("yes", "true", "1") or t.get("junction") == "roundabout"; rev = t.get("oneway") == "-1"
            for a, b in zip(e["nodes"], e["nodes"][1:]):
                if a in nodes and b in nodes:
                    d = hav_km(nodes[a], nodes[b])
                    if rev: g.add_edge(b, a, length=d)
                    else:
                        g.add_edge(a, b, length=d)
                        if not one: g.add_edge(b, a, length=d)
        g = g.subgraph(max(nx.strongly_connected_components(g), key=len)).copy()
        return g, {n: nodes[n] for n in g.nodes}

    def _init_roads(self, tol=0.002):
        pts = [(p["lat"], p["lon"]) for p in self.places]
        lat0, lat1 = min(p[0] for p in pts), max(p[0] for p in pts); lon0, lon1 = min(p[1] for p in pts), max(p[1] for p in pts)
        s, n, w, e = lat0 - .01, lat1 + .01, lon0 - .01, lon1 + .01
        hwy = HWY_MAIN if (n - s) * (e - w) > .004 else HWY_ALL
        data, cache = None, os.path.join(DATA, f"roads_{self.key}.json")
        if os.path.exists(cache):
            c = json.load(open(cache)); b = c["bbox"]
            if b[0] <= lat0 + tol and b[1] <= lon0 + tol and b[2] >= lat1 - tol and b[3] >= lon1 - tol: data = c["data"]
        if data is None and not OFFLINE:
            data = self._fetch_roads(s, w, n, e, hwy)
            if data:
                try: json.dump({"bbox": [s, w, n, e], "data": data}, open(cache, "w"))
                except OSError: pass
        if data:
            try:
                self.G, self.xy = self._build_graph(data)
                self.routing = f"OpenStreetMap road network ({self.G.number_of_nodes()} junctions, {self.G.number_of_edges()} segments)"
            except ValueError: self.G = None
        if self.G is None: print(f"[{self.key}] no road data - straight-line x {ROAD_FACTOR}")

    def snap(self, lat, lon):
        return min(self.xy, key=lambda k: hav_km((lat, lon), self.xy[k])) if self.G is not None else None

    def _sp(self, src):
        if src not in self.SP: self.SP[src] = nx.single_source_dijkstra(self.G, src, weight="length")
        return self.SP[src]

    def dist(self, a, b):                                          # km along roads
        if self.G is None: return hav_km((a["lat"], a["lon"]), (b["lat"], b["lon"])) * ROAD_FACTOR
        return 0.0 if a["node"] == b["node"] else self._sp(a["node"])[0].get(b["node"], 1e9)

    def leg(self, a, b):
        if self.G is None or a["node"] == b["node"] or b["node"] not in self._sp(a["node"])[1]:
            return [[a["lat"], a["lon"]], [b["lat"], b["lon"]]]
        return [list(self.xy[n]) for n in self._sp(a["node"])[1][b["node"]]]

    # ---------- state ----------
    def reset(self):
        with self.lock:
            rng = random.Random(zlib.crc32(self.key.encode())); self.P = []
            for i, p in enumerate(self.places):
                area = p.get("area") or rng.choice([600, 900, 1200, 1800])
                self.P.append(dict(id=f"V{i+1:02d}", name=p["name"], kind=p.get("kind", "venue"), lat=p["lat"], lon=p["lon"], node=self.snap(p["lat"], p["lon"]), area=area,
                                   gate_w=p.get("gate") or round(max(2, area ** .5 / 8), 1), pop=p.get("pop") or round(rng.uniform(.5, 2.2), 2),
                                   dwell=p.get("dwell") or rng.choice([15, 20, 25, 30]), count=area * SAFE * rng.uniform(.1, .5), queue=0.0, gate="OPEN",
                                   flagged=False, extra=0.0, arr_min=0.0, last_report=None, pop_adj=1.0, last_obs=None, anomaly=None))
                self.P[-1]["_seen"] = dict(lv=level(density(self.P[-1])), gate="OPEN", flag=False, anom=None, danger_t=0.0)
            cal = os.path.join(DATA, self.key + "_calibration.json")
            if os.path.exists(cal):                                  # values fitted from real history (see calibrate.py)
                for vid, c in json.load(open(cal)).items():
                    p = self.find(vid)
                    if p: p["pop"], p["dwell"] = c["pop"], c["dwell"]
            self._mc = {}; self.EVENTS = []
            speed = self.STATE["speed"] if hasattr(self, "STATE") else SIM_SPEED
            self.REPORTS = []; self.STATE = {"t": time.time(), "hour": self.start_hour, "day": self.start_day, "auto": False, "speed": speed}
            self.NEIGH = {p["id"]: [q["id"] for q in sorted((q for q in self.P if q is not p), key=lambda q: hav_km((p["lat"], p["lon"]), (q["lat"], q["lon"])))
                                    if hav_km((p["lat"], p["lon"]), (q["lat"], q["lon"])) * ROAD_FACTOR <= DIVERT_MAX_KM][:4] for p in self.P}

    def hour_mult(self, h): return self.base + sum(w * _bump(h, c, wd) for c, wd, w in self.peaks)

    def tick(self):
        with self.lock:
            S = self.STATE; now = time.time(); dt = min(10, (now - S["t"]) * S["speed"] / 60); S["t"] = now
            if dt <= 0: return
            S["hour"] = (S["hour"] + dt / 60) % 24
            hm, dm = self.hour_mult(S["hour"]), self.days[S["day"]]
            if S["auto"]:
                for p in self.P: p["gate"] = gate_for(p)
            by = {p["id"]: p for p in self.P}; nxt = {p["id"]: 0.0 for p in self.P}
            for p in self.P: step(p, dt, hm, dm, nxt, by, self.NEIGH)
            for p in self.P: p["extra"] += nxt[p["id"]]
            self._detect()

    # ---------- alert events (for voice / banners) ----------
    def _emit(self, code, p, sev, x=""):
        self.seq += 1; h = self.STATE["hour"]
        self.EVENTS.append(dict(seq=self.seq, at=time.strftime("%H:%M:%S"), sim=f"{int(h):02d}:{int(h % 1 * 60):02d}", sev=sev, code=code, vid=p["id"], name=p["name"], x=x))
        del self.EVENTS[:-200]

    def _detect(self):
        """Compare every venue with what we last announced and emit events: crowded, critical (+60 s reminders), gate changes, alerts, jumps, recovery."""
        now = time.time()
        for p in self.P:
            s = p["_seen"]; lv = level(density(p)); up = LEVEL_RANK[lv] - LEVEL_RANK[s["lv"]]
            if up > 0 and lv == "critical": self._emit("critical", p, "danger"); s["danger_t"] = now
            elif up > 0 and lv == "crowded": self._emit("crowded", p, "warning")
            elif lv == "critical" and now - s["danger_t"] >= 60: self._emit("reminder", p, "danger"); s["danger_t"] = now
            elif up < 0 and s["lv"] in ("crowded", "critical") and LEVEL_RANK[lv] <= 1: self._emit("recovered", p, "info")
            if p["gate"] != s["gate"]:
                if p["gate"] == "CLOSED":
                    alts = self.alternates(p)[0]; self._emit("closed", p, "warning", alts[0]["name"] if alts else "")
                elif p["gate"] == "METERED": self._emit("metered", p, "info")
            if p["flagged"] and not s["flag"]: self._emit("alert", p, "danger", p["last_report"] or "crush risk")
            if p["anomaly"] and p["anomaly"] != s["anom"]: self._emit("jump", p, "warning")
            s.update(lv=lv, gate=p["gate"], flag=p["flagged"], anom=p["anomaly"])

    def events_since(self, since=None, lang="en"):
        """New alert events after number `since` (None = just return the latest number), with text in en / hi / bn."""
        with self.lock:
            since = self.seq if since is None else int(since)
            evs = [dict(seq=e["seq"], at=e["at"], sim=e["sim"], sev=e["sev"], code=e["code"], vid=e["vid"], name=e["name"], text=render_event(e, lang)) for e in self.EVENTS if e["seq"] > since]
            return dict(seq=self.seq, events=evs[-20:])

    # ---------- forecast ----------
    def simulate(self, horizon=180, controlled=False, dt=5, rng=None):
        """Forecast on a copy of the live state. controlled=False -> every gate stays open (no intervention)."""
        ps = [dict(p) for p in self.P]; by = {p["id"]: p for p in ps}; h = self.STATE["hour"]; dm = self.days[self.STATE["day"]]
        if not controlled:
            for p in ps: p["gate"] = "OPEN"
        series, first, peak, d30, danger = [], {}, {p["id"]: density(p) for p in ps}, {}, 0.0
        xs = {p["id"]: 0.0 for p in ps}                              # slowly varying random arrival noise per venue (Monte Carlo only)
        for k in range(1, horizon // dt + 1):
            h = (h + dt / 60) % 24; hm = self.hour_mult(h); nxt = {p["id"]: 0.0 for p in ps}
            for p in ps:
                if controlled: p["gate"] = gate_for(p)
                m = 1.0
                if rng:
                    xs[p["id"]] = .8 * xs[p["id"]] + rng.gauss(0, NOISE_SIGMA); m = math.exp(xs[p["id"]])
                    if rng.random() < SURGE_P: p["extra"] += SURGE_FRAC * cap(p)
                step(p, dt, hm, dm, nxt, by, self.NEIGH, m)
            for p in ps:
                p["extra"] += nxt[p["id"]]; d = density(p)
                peak[p["id"]] = max(peak[p["id"]], d)
                if d >= CRIT: first.setdefault(p["id"], k * dt)
                danger += max(0.0, p["count"] - CRIT * p["area"]) * dt
                if k * dt == 30: d30[p["id"]] = d
            ds = [density(p) for p in ps]
            series.append(dict(t=f"{int(h):02d}:{int(h % 1 * 60):02d}", crit=sum(d >= CRIT for d in ds), warn=sum(d >= WARN for d in ds), max_d=round(max(ds), 2)))
        return dict(series=series, first=first, peak=peak, d30=d30, danger=round(danger), crit_pandals=sum(v >= CRIT for v in peak.values()), peak_d=round(max(peak.values()), 2))

    def forecast(self):
        with self.lock:
            unc, ctl = self.simulate(180, False), self.simulate(180, True)
            mu, mc_ = self.mc_forecast(False), self.mc_forecast(True)
            rank = sorted(({"id": p["id"], "name": p["name"], "now": round(density(p), 2), "d30": round(unc["d30"][p["id"]], 2), "peak": round(unc["peak"][p["id"]], 2),
                            "to_crit_min": unc["first"].get(p["id"]), "p60": mu["p"][p["id"]]["60"]} for p in self.P), key=lambda r: -r["peak"])
        return dict(unc=unc["series"], ctl=ctl["series"], rank=rank[:10], band_unc=mu["bands"], band_ctl=mc_["bands"], p_any_unc=mu["p_any"], p_any_ctl=mc_["p_any"], uncontrolled=dict(danger=unc["danger"], crit=unc["crit_pandals"], peak=unc["peak_d"]),
                    controlled=dict(danger=ctl["danger"], crit=ctl["crit_pandals"], peak=ctl["peak_d"]))

    def mc_forecast(self, controlled=False, runs=40, horizon=120, ttl=4):
        """Monte Carlo forecast: many noisy futures -> chance of reaching 4/m2 and uncertainty bands for the busiest venue."""
        with self.lock:
            c = self._mc.get(controlled)
            if c and time.time() - c[0] < ttl: return c[1]
            rng = random.Random(int(time.time()) // 5); n = horizon // 5
            cols, ts, hits, any_hit = [[] for _ in range(n)], [], {p["id"]: {30: 0, 60: 0, 120: 0} for p in self.P}, 0
            for _ in range(runs):
                r = self.simulate(horizon, controlled, 5, rng)
                for k, sr in enumerate(r["series"]): cols[k].append(sr["max_d"]); ts = [x["t"] for x in r["series"]]
                any_hit += bool(r["first"])
                for i, m in r["first"].items():
                    for T in hits[i]:
                        if m <= T: hits[i][T] += 1
            pct = lambda a, q: sorted(a)[min(len(a) - 1, int(q * len(a)))]
            out = dict(runs=runs, p_any=round(any_hit / runs, 2), p={i: {str(T): round(v / runs, 2) for T, v in h.items()} for i, h in hits.items()},
                       bands=[dict(t=ts[k], p10=round(pct(c_, .1), 2), p50=round(pct(c_, .5), 2), p90=round(pct(c_, .9), 2)) for k, c_ in enumerate(cols)])
            self._mc[controlled] = (time.time(), out); return out

    def risk(self, p, d30):
        """0-100 early-warning score from density now, density in ~20 min, trend, queue, inflow vs outflow and alerts - with reasons."""
        d = density(p); d20 = d + (d30 - d) * 20 / 30; out_min = p["count"] / p["dwell"]
        c = dict(now=min(1, d / CRIT), soon=min(1, d20 / CRIT), trend=max(0, min(1, (d20 - d) / 1.0)), queue=min(1, p["queue"] / (cap(p) * .5)),
                 flux=min(1, max(0, p["arr_min"] / max(1, out_min) - 1)))
        score = 100 * (.35 * c["now"] + .30 * c["soon"] + .10 * c["trend"] + .10 * c["queue"] + .10 * c["flux"]) + (15 if p["flagged"] else 0)
        if d >= CRIT or d20 >= CRIT: score = max(score, 85)
        elif d >= WARN or d20 >= WARN: score = max(score, 60)
        why = ([f"{d:.1f} people/m² now"] if d >= WARN else []) + ([f"rising to ~{d20:.1f} in 20 min"] if d20 - d >= .4 else []) + (["long queue outside"] if c["queue"] > .3 else []) + \
              (["more arriving than leaving"] if c["flux"] > .3 else []) + (["citizen alert"] if p["flagged"] else []) + (["sudden jump in counts"] if p["anomaly"] and time.time() - p["anomaly"] < 600 else [])
        if not why and score >= 40: why = ["building toward a crowded state"]
        return min(100, round(score)), why

    def calibrate(self, rows, save=True):
        """Fit each venue's popularity and visit time to real history. rows: dicts with venue_id, hour (0-24), count, optional day."""
        by = {}
        for r in rows: by.setdefault((r["venue_id"], r.get("day") or self.STATE["day"]), []).append((float(r["hour"]), float(r["count"])))
        best_of = {}
        for (vid, day), obs in by.items():
            if len(obs) >= 4 and (vid not in best_of or len(obs) > best_of[vid][2]): best_of[vid] = (day, sorted(obs), len(obs))
        res = {}
        for vid, (day, obs, n) in best_of.items():
            p = self.find(vid)
            if not p or n < 4: continue
            dm = self.days.get(day, self.days[self.STATE["day"]]); best = None
            for pop in [x / 10 for x in range(3, 31)]:
                for dw in (10, 15, 20, 25, 30, 40, 60, 90):
                    q = dict(p, pop=pop, dwell=dw); e = self._replay(q, obs, dm)
                    if best is None or e < best[0]: best = (e, pop, dw)
            base = self._replay(dict(p), obs, dm)
            res[vid] = dict(pop=best[1], dwell=best[2], mae_before=round(base, 3), mae_after=round(best[0], 3), points=n)
        if save and res:
            with open(os.path.join(DATA, self.key + "_calibration.json"), "w") as f: json.dump({k: dict(pop=v["pop"], dwell=v["dwell"]) for k, v in res.items()}, f, indent=1)
        return res

    def _replay(self, p, obs, dm):
        """Replay one venue (gates open) from its first observation; mean absolute error in people/m2 at the later observations."""
        q = dict(p, count=obs[0][1], queue=0.0, gate="OPEN", extra=0.0, pop_adj=1.0); t = obs[0][0]; err = 0.0
        for h, c in obs[1:]:
            gap = (h - t) % 24 * 60; n = max(1, round(gap / 5)); dt = gap / n if gap else 1
            for k in range(n): step(q, dt, self.hour_mult((t + k * dt / 60) % 24), dm, {q["id"]: 0.0}, {q["id"]: q}, {q["id"]: []})
            err += abs(q["count"] - c) / q["area"]; t = h
        return err / (len(obs) - 1)

    # ---------- actions ----------
    def alternates(self, p, k=2):
        c = [(q, self.dist(p, q)) for q in self.P if q is not p and q["gate"] == "OPEN" and density(q) < SAFE + .5]
        c = sorted([x for x in c if x[1] <= DIVERT_MAX_KM + 1], key=lambda x: x[1] + .3 * density(x[0]))[:k]
        return [dict(id=q["id"], name=q["name"], km=round(d, 2), walk_min=round(d / WALK_KMH * 60), density=round(density(q), 2)) for q, d in c], c

    def nearest_exit(self, p):
        if not self.exits: return None
        x = min(self.exits, key=lambda e: hav_km((p["lat"], p["lon"]), (e["lat"], e["lon"])))
        return x, self.dist(p, x)

    def plan_core(self):
        with self.lock:
            unc = self.simulate(120, False); ctl = self.simulate(120, True); mu, mc_ = self.mc_forecast(False), self.mc_forecast(True)
            d20 = {p["id"]: density(p) + (unc["d30"].get(p["id"], density(p)) - density(p)) * 20 / 30 for p in self.P}
            eff = {p["id"]: max(density(p), d20[p["id"]]) + (.7 if p["flagged"] else 0) for p in self.P}
            for p in self.P:                                          # act early when the chance of a crush is high, not only when density is
                p30 = mu["p"][p["id"]]["30"]
                if p30 >= .40: eff[p["id"]] = max(eff[p["id"]], CLOSE_AT)
                elif p30 >= .15 or mu["p"][p["id"]]["60"] >= .50: eff[p["id"]] = max(eff[p["id"]], METER_AT)
            gates = {p["id"]: gate_for(p, eff[p["id"]]) for p in self.P}
            w = {p["id"]: max(0, eff[p["id"]] - 1.5) ** 2 * math.sqrt(p["area"]) for p in self.P}; tw = sum(w.values()) or 1
            officers = {i: (max(2, round(N_OFFICERS * v / tw)) if eff[i] >= WARN else round(N_OFFICERS * v / tw)) for i, v in w.items()}
            actions = []
            for p in sorted(self.P, key=lambda p: -eff[p["id"]]):
                i = p["id"]
                if gates[i] == "OPEN" and eff[i] < WARN: continue
                alts, raw = self.alternates(p); ex = self.nearest_exit(p)
                why = f'{density(p):.1f} people/m² now, ~{d20[i]:.1f} in 20 min' + (", citizen alert raised" if p["flagged"] else "") + \
                      (f', {round(mu["p"][i]["30"] * 100)}% chance of 4/m² within 30 min' if mu["p"][i]["30"] >= .05 else
                       f', {round(mu["p"][i]["60"] * 100)}% chance of 4/m² within 1 h' if mu["p"][i]["60"] >= .10 else "")
                rs, rwhy = self.risk(p, unc["d30"].get(i, density(p)))
                msg = ("Entry stopped. Please use " + alts[0]["name"] + f" ({alts[0]['walk_min']} min walk)") if gates[i] == "CLOSED" and alts else \
                      "Entry stopped. Hold people back safely and open a dispersal route." if gates[i] == "CLOSED" else \
                      "One-in-one-out. Expect a wait." if gates[i] == "METERED" else "Crowd building - stewards on alert."
                actions.append(dict(id=i, name=p["name"], kind=p["kind"], gate=gates[i], current_gate=p["gate"], why=why, officers=officers[i], density=round(density(p), 2),
                                    d20=round(d20[i], 2), alternates=alts, divert_path=self.leg(p, raw[0][0]) if raw else [],
                                    exit=dict(name=ex[0]["name"], km=round(ex[1], 2), path=self.leg(p, ex[0])) if ex else None, to_crit_min=unc["first"].get(i), message=msg,
                                    risk=rs, risk_why=rwhy, p30=mu["p"][i]["30"], p60=mu["p"][i]["60"]))
            summ = lambda s: dict(peak_density=s["peak_d"], pandals_critical=s["crit_pandals"], danger_person_min=s["danger"])
            return dict(actions=actions, gates=gates, officers={k: v for k, v in officers.items() if v}, uncontrolled=summ(unc), controlled=summ(ctl),
                        p_any_uncontrolled=mu["p_any"], p_any_controlled=mc_["p_any"], routing=self.routing, n_officers=N_OFFICERS)

    def apply_plan(self):
        with self.lock:
            pc = self.plan_core()
            for p in self.P: p["gate"] = pc["gates"][p["id"]]
            self._mc = {}; self._detect()
            return sum(g != "OPEN" for g in pc["gates"].values())

    def route_core(self, lat, lon, n=4):
        """Crowd-aware walking route: greedy, trading distance against current and expected density."""
        with self.lock:
            d30 = self.simulate(60, False)["d30"]; cur = dict(name="You", lat=lat, lon=lon, node=self.snap(lat, lon)); left = list(self.P); stops, path, tot = [], [], 0.0
            for _ in range(n):
                cand = [p for p in left if density(p) < WARN and d30[p["id"]] < CRIT and p["gate"] != "CLOSED"]
                if not cand: break
                nx_ = min(cand, key=lambda p: self.dist(cur, p) + .8 * max(0, density(p) - 1.5) + .8 * max(0, d30[p["id"]] - 1.5))
                d = self.dist(cur, nx_); seg = self.leg(cur, nx_); path += seg if not path else seg[1:]; tot += d
                stops.append(dict(id=nx_["id"], name=nx_["name"], km=round(d, 2), walk_min=round(d / WALK_KMH * 60), density=round(density(nx_), 2), level=level(density(nx_)),
                                  wait_min=round(nx_["queue"] / max(1, nx_["count"] / nx_["dwell"])) if nx_["queue"] > 20 else 0))
                cur = nx_; left.remove(nx_)
            skipped = [dict(name=p["name"], level=level(density(p))) for p in self.P if density(p) >= WARN or p["gate"] == "CLOSED"]
        return dict(stops=stops, path=path, km=round(tot, 2), walk_min=round(tot / WALK_KMH * 60), skipped=skipped)

    # ---------- live data in / demo controls ----------
    def snapshot(self):
        with self.lock:
            rows = []; d30 = self.simulate(30, False)["d30"]
            for p in self.P:
                d = density(p); out = p["count"] / p["dwell"]; rs, rwhy = self.risk(p, d30.get(p["id"], d))
                rows.append(dict(id=p["id"], name=p["name"], kind=p["kind"], lat=p["lat"], lon=p["lon"], area=p["area"], count=round(p["count"]), queue=round(p["queue"]), density=round(d, 2),
                                 level=level(d), gate=p["gate"], flagged=p["flagged"], arr_min=round(p["arr_min"]), wait_min=round(p["queue"] / max(1, out)) if p["queue"] > 20 else 0,
                                 last_report=p["last_report"], risk=rs, risk_why=rwhy, learn=round(p["pop_adj"], 2)))
            h = self.STATE["hour"]
            return dict(site=self.key, title=self.title, note=self.note, venues=rows, exits=[{k: x[k] for k in ("name", "lat", "lon")} for x in self.exits],
                        sim_time=f"{int(h):02d}:{int(h % 1 * 60):02d}", day=self.STATE["day"], days=list(self.days), auto=self.STATE["auto"], speed=self.STATE["speed"], reports=self.REPORTS[-20:],
                        source=self.source, routing=self.routing, thresholds=dict(safe=SAFE, warn=WARN, crit=CRIT),
                        totals=dict(people=sum(r["count"] for r in rows), queue=sum(r["queue"] for r in rows), critical=sum(r["level"] == "critical" for r in rows),
                                    crowded=sum(r["level"] == "crowded" for r in rows)))

    def find(self, vid): return next((p for p in self.P if p["id"] == vid), None)

    def telemetry(self, vid, count=None, density_=None, queue=None):
        """Real counts from cameras / turnstiles / volunteers: set people inside (count or density) and optionally the queue."""
        with self.lock:
            p = self.find(vid)
            if not p: return False
            obs = max(0.0, float(count)) if count is not None else max(0.0, float(density_)) * p["area"] if density_ is not None else None
            if obs is not None:
                pred = p["count"]                                    # what the model expected before this reading
                if pred > 50:                                        # self-correct: nudge learned arrival intensity toward reality
                    p["pop_adj"] = max(.3, min(4.0, p["pop_adj"] * (max(obs, 1) / pred) ** .3))
                    if obs > pred * 1.6 and obs - pred > .3 * cap(p): p["anomaly"] = time.time()    # sudden jump: surge or sensor fault
                p["count"] = obs
            if queue is not None: p["queue"] = max(0.0, float(queue))
            self._mc = {}; self._detect(); return True

    def report(self, vid, kind="crush risk"):
        with self.lock:
            p = self.find(vid)
            if not p: return False
            p["flagged"] = True; p["last_report"] = kind; self._mc = {}; self._detect()
            self.REPORTS.append(dict(venue_id=p["id"], name=p["name"], type=kind, at=time.strftime("%H:%M:%S")))
            return True

    def clear_alerts(self, ids=None):
        with self.lock:
            for p in self.P:
                if not ids or p["id"] in ids: p["flagged"] = False; p["last_report"] = None

    def scenario(self, day=None, auto=None, hour=None, venue_id=None, surge=None, speed=None):
        """Demo controls. surge = fraction of the venue's safe capacity added at once (e.g. 0.6)."""
        with self.lock:
            if day in self.days: self.STATE["day"] = day
            self._mc = {}
            if auto is not None: self.STATE["auto"] = bool(auto)
            if speed is not None: self.STATE["speed"] = max(1.0, min(600.0, float(speed)))
            if hour is not None: self.STATE["hour"] = float(hour) % 24
            p = self.find(venue_id)
            if p and surge is not None: p["count"] += float(surge) * cap(p)
            self._detect()

# ---------------- registry ----------------
DEFAULT = next(iter(CATALOG))
SITES, _SL = {}, threading.Lock()

def get_site(key=None):
    key = key if key in CATALOG else DEFAULT
    with _SL:
        if key not in SITES: SITES[key] = Site(key)
    return SITES[key]

def site_list():
    return [dict(key=k, title=c["title"], note=c.get("note", ""), n=len(c["venues"])) for k, c in CATALOG.items()]
