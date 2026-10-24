"""CrowdSafe India - Streamlit app. Pick a crowded place (Kolkata, Mumbai, Haridwar, Prayagraj ...) and see the live crowd,
the forecast, gate-control plan and a calm walking route. The crowd model lives in engine.py; places are listed in places.py.
Run:  streamlit run streamlit_app.py      Deploy: share.streamlit.io -> main file = streamlit_app.py
Note: crowd state lives in this server process, so everyone viewing the same place sees the same crowd.
"""
import time
import pandas as pd, pydeck as pdk, streamlit as st
import engine, voice

st.set_page_config(page_title="CrowdSafe India", page_icon="🚦", layout="wide")
RGB = {"calm": [63, 184, 165], "busy": [232, 177, 58], "crowded": [240, 122, 43], "critical": [229, 56, 79]}
GATE_RGB = {"OPEN": [14, 22, 33], "METERED": [167, 139, 250], "CLOSED": [255, 255, 255]}
BASEMAP = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

# ---------------- sidebar: choose the place ----------------
sites = {s["key"]: s for s in engine.site_list()}
with st.sidebar:
    st.title("CrowdSafe India")
    key = st.selectbox("Place", list(sites), format_func=lambda k: sites[k]["title"], index=list(sites).index(engine.DEFAULT))
    st.caption(sites[key]["note"])
with st.spinner("Loading this place (the first time it downloads the road map, about a minute)..."):
    site = engine.get_site(key)

def rows():
    out = []
    for v in site.snapshot()["venues"]:
        out.append(dict(id=v["id"], Venue=v["name"], Type=v["kind"], lat=v["lat"], lon=v["lon"], People=v["count"], Density=v["density"], Level=v["level"], Gate=v["gate"],
                        Waiting=v["queue"], Wait_min=v["wait_min"], Alert=v["last_report"] or "", Risk=v["risk"], Why=", ".join(v["risk_why"]),
                        color=RGB[v["level"]], line=GATE_RGB[v["gate"]]))
    return pd.DataFrame(out)

def swap(path): return [[x[1], x[0]] for x in path]       # [lat,lon] -> [lon,lat] for pydeck

def draw(df, paths=(), height=520):
    pts = [[v["lon"], v["lat"]] for v in site.P]
    layers = [pdk.Layer("ScatterplotLayer", df, get_position="[lon, lat]", get_fill_color="color", get_line_color="line", get_radius=95, stroked=True,
                        line_width_min_pixels=3, pickable=True, radius_min_pixels=7)]
    ex = pd.DataFrame([dict(Venue=x["name"], lat=x["lat"], lon=x["lon"]) for x in site.exits])
    if len(ex): layers.append(pdk.Layer("ScatterplotLayer", ex, get_position="[lon, lat]", get_fill_color=[14, 22, 33], get_line_color=[232, 237, 243], stroked=True,
                                        get_radius=55, line_width_min_pixels=2, radius_min_pixels=4, pickable=True))
    for p, colr in paths:
        if p: layers.append(pdk.Layer("PathLayer", [dict(path=swap(p))], get_path="path", get_color=colr, width_min_pixels=4))
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.data_utils.compute_view(pts), map_style=BASEMAP, height=height,
                             tooltip={"text": "{Venue}\n{People} inside · {Density} people/m²\nGate: {Gate} · {Waiting} waiting"}), key=f"map_{key}_{height}")

# ---------------- sidebar: festival controls and demo tools ----------------
with st.sidebar:
    days = list(site.days)
    site.STATE["day"] = st.selectbox("Day / occasion", days, index=days.index(site.STATE["day"]), key=f"day_{key}")
    site.STATE["auto"] = st.toggle("Auto-control gates", value=site.STATE["auto"], key=f"auto_{key}", help="The controller opens, meters or closes gates by itself.")
    speeds = {"Real time (1x)": 1, "Slow (10x)": 10, "Normal (30x)": 30, "Fast (120x)": 120}
    cur = min(speeds, key=lambda k: abs(speeds[k] - site.STATE["speed"]))
    site.STATE["speed"] = speeds[st.selectbox("Simulation speed", list(speeds), index=list(speeds).index(cur), key=f"spd_{key}", help="How fast the clock runs. 30x: one real second = 30 simulated seconds.")]
    st.divider(); st.caption("Voice alerts")
    voice_on = st.toggle("Spoken alerts", key="voice_on", help="Plays a spoken warning (or a siren if offline) when a venue gets crowded or critical. Click this once so the browser allows sound.")
    langs = {"English": "en", "हिन्दी": "hi", "বাংলা": "bn"}
    lang = langs[st.selectbox("Voice language", list(langs), key="voice_lang")]
    st.divider(); st.caption("Demo and alerts")
    names = {p["id"]: p["name"] for p in site.P}
    vid = st.selectbox("Venue", list(names), format_func=names.get, key=f"vid_{key}")
    if st.button("Simulate a crowd surge", width="stretch"): site.scenario(venue_id=vid, surge=0.6)
    kind = st.selectbox("Alert type", ["crush risk", "blocked exit", "panic", "medical emergency"])
    c1, c2 = st.columns(2)
    if c1.button("Raise alert", width="stretch"): site.report(vid, kind)
    if c2.button("Clear alerts", width="stretch"): site.clear_alerts()
    if st.button("Reset this place", width="stretch"):
        site.reset(); st.session_state.pop("plan", None); st.rerun()
    st.caption(f"{len(site.P)} venues · {site.source}")

tab_live, tab_plan, tab_fc, tab_visit, tab_about = st.tabs(["Live crowd", "Action plan", "Next 3 hours", "Visit safely", "About"])

# ---------------- live (refreshes every 2 s) ----------------
with tab_live:
    @st.fragment(run_every=2)
    def live():
        site.tick(); df = rows(); h = site.STATE["hour"]
        sk, lk, now = f"seq_{key}", f"log_{key}", time.time()
        if sk not in st.session_state: st.session_state[sk] = site.seq; st.session_state[lk] = []
        ev = site.events_since(st.session_state[sk], lang); st.session_state[sk] = ev["seq"]
        if ev["events"]:
            st.session_state[lk] = (ev["events"][::-1] + st.session_state[lk])[:8]
            loud = [e for e in ev["events"] if e["sev"] != "info" or e["code"] == "closed"]
            if loud:
                if any(e["sev"] == "danger" for e in loud): st.session_state["banner"] = (next(e["text"] for e in loud if e["sev"] == "danger"), now + 10)
                if voice_on:
                    top = sorted(loud, key=lambda e: e["sev"] != "danger")[:2]
                    data, mime = voice.make_clip(" ".join(e["text"] for e in top), lang, "danger" if top[0]["sev"] == "danger" else "warning")
                    st.session_state["clip"] = (data, mime, now + 14)
        if st.session_state.get("banner", ("", 0))[1] > now: st.error(st.session_state["banner"][0], icon="🚨")
        clip = st.session_state.get("clip")
        if voice_on and clip and clip[2] > now: st.audio(clip[0], format=clip[1], autoplay=True)
        a, b, c, d = st.columns(4)
        a.metric("Simulated time", f"{int(h):02d}:{int(h % 1 * 60):02d}"); b.metric("People inside", f"{int(df.People.sum()):,}")
        c.metric("Crowded (≥3/m²)", int((df.Density >= engine.WARN).sum())); d.metric("Critical (≥4/m²)", int((df.Density >= engine.CRIT).sum()))
        draw(df)
        if st.session_state.get(lk):
            with st.expander("Alert log", expanded=False):
                for e in st.session_state[lk]: st.write(f'{e["at"]} · {e["text"]}')
        st.dataframe(df.sort_values("Density", ascending=False)[["Venue", "Type", "Risk", "Density", "Level", "Gate", "People", "Waiting", "Wait_min", "Why", "Alert"]], hide_index=True, width="stretch",
                     column_config={"Risk": st.column_config.ProgressColumn("Risk (0-100)", min_value=0, max_value=100, format="%d"), "Density": st.column_config.ProgressColumn("People/m²", min_value=0, max_value=5, format="%.1f"), "Wait_min": "Wait (min)"})
    live()

# ---------------- action plan ----------------
with tab_plan:
    st.caption("Looks two hours ahead and decides, venue by venue: keep open, one-in-one-out, or stop entry and divert.")
    c1, c2 = st.columns(2)
    if c1.button("Compute plan", type="primary"):
        site.tick(); st.session_state["plan"] = (key, site.plan_core())
    if c2.button("Apply gate controls"):
        site.apply_plan(); st.session_state["plan"] = (key, site.plan_core()); st.toast("Gate controls applied")
    saved = st.session_state.get("plan"); pl = saved[1] if saved and saved[0] == key else None
    if pl:
        u, c = pl["uncontrolled"], pl["controlled"]; x, y = st.columns(2)
        x.metric("Peak density, no intervention", f'{u["peak_density"]}/m²', f'{u["pandals_critical"]} venue(s) critical', delta_color="off")
        y.metric("Peak density, with controls", f'{c["peak_density"]}/m²', f'{c["pandals_critical"]} venue(s) critical', delta_color="off")
        st.metric("Chance some venue reaches 4/m² within 2 hours", f'{round(pl["p_any_uncontrolled"] * 100)}% without controls', f'{round(pl["p_any_controlled"] * 100)}% with controls', delta_color="off")
        st.caption(f'Person-minutes above 4/m² (central forecast): {u["danger_person_min"]:,} without controls, {c["danger_person_min"]:,} with controls.')
        draw(rows(), [(a["divert_path"], [94, 177, 255]) for a in pl["actions"]] + [(a["exit"]["path"], [232, 237, 243]) for a in pl["actions"] if a["exit"]], 420)
        if not pl["actions"]: st.success("No venue needs action right now.")
        for a in pl["actions"]:
            with st.expander(f'{a["name"]} · {"watch" if a["gate"] == "OPEN" else a["gate"].lower()} · {a["density"]}/m²', expanded=a["gate"] == "CLOSED"):
                st.write(a["why"] + (f' · reaches 4/m² in about {a["to_crit_min"]} min if left alone' if a["to_crit_min"] else ""))
                st.write(f'Risk **{a["risk"]}/100**' + (" · " + ", ".join(a["risk_why"]) if a["risk_why"] else ""))
                st.write(f'**{a["officers"]}** of {pl["n_officers"]} officers here. {a["message"]}')
                st.write("Divert to: " + (" or ".join(f'{z["name"]} ({z["walk_min"]} min walk, {z["density"]}/m²)' for z in a["alternates"]) or "no calm venue within walking distance"))
                if a["exit"]: st.caption(f'Dispersal exit: {a["exit"]["name"]}, {a["exit"]["km"]} km')

# ---------------- forecast ----------------
with tab_fc:
    st.caption("If nobody intervenes, versus the controller, over the next 3 hours.")
    if st.button("Run forecast", type="primary") or st.session_state.get("fc") == key:
        st.session_state["fc"] = key; f = site.forecast(); t = [r["t"] for r in f["unc"]]
        st.metric("Chance some venue reaches 4/m² within 2 hours", f'{round(f["p_any_unc"] * 100)}% without controls', f'{round(f["p_any_ctl"] * 100)}% with controls', delta_color="off")
        st.line_chart(pd.DataFrame({"no intervention (median)": [b["p50"] for b in f["band_unc"]], "no intervention (bad case, 90th pct)": [b["p90"] for b in f["band_unc"]],
                                    "with controls (median)": [b["p50"] for b in f["band_ctl"]], "with controls (bad case, 90th pct)": [b["p90"] for b in f["band_ctl"]]},
                                   index=[b["t"] for b in f["band_unc"]]), y_label="Busiest venue, people/m² (2 h, from 40 noisy simulations)")
        st.line_chart(pd.DataFrame({"no intervention": [r["crit"] for r in f["unc"]], "with controls": [r["crit"] for r in f["ctl"]]}, index=t), y_label="Venues above 4/m²")
        st.subheader("Likeliest trouble spots")
        st.dataframe(pd.DataFrame(f["rank"]).rename(columns={"name": "Venue", "now": "Now", "d30": "In 30 min", "peak": "Peak", "to_crit_min": "Minutes to 4/m²", "p60": "Chance of 4/m² in 1 h"})[["Venue", "Now", "In 30 min", "Peak", "Minutes to 4/m²", "Chance of 4/m² in 1 h"]], hide_index=True, width="stretch")

# ---------------- visitor route ----------------
with tab_visit:
    st.caption("Get a walking route through venues that are calm now and expected to stay calm.")
    start = st.selectbox("Start near", list(names), format_func=names.get, key=f"start_{key}")
    n = st.slider("Number of stops", 2, 6, min(4, len(names)))
    if st.button("Plan my route", type="primary"):
        sp = next(p for p in site.P if p["id"] == start); site.tick()
        r = site.route_core(sp["lat"], sp["lon"], n)
        if r["stops"]:
            st.success(f'{len(r["stops"])} stops · {r["km"]} km · about {r["walk_min"]} min walking')
            st.dataframe(pd.DataFrame(r["stops"])[["name", "density", "level", "walk_min", "wait_min"]].rename(columns={"name": "Venue", "density": "People/m²", "level": "Crowd", "walk_min": "Walk (min)", "wait_min": "Queue (min)"}), hide_index=True, width="stretch")
            draw(rows(), [(r["path"], [63, 184, 165])], 420)
        else: st.warning("No calm venue is reachable right now. Try again in a few minutes.")
        if r["skipped"]: st.caption("Avoided for now: " + ", ".join(s["name"] for s in r["skipped"]))

# ---------------- about ----------------
with tab_about:
    st.markdown(f"""
**Place.** {site.title}. {len(site.P)} venues and {len(site.exits)} exits from `{site.source}`. Routing: {site.routing}.

**Model.** Each venue is a small queueing system: arrivals follow this place's daily peaks and the chosen day or occasion, people stay for a typical visit time (longer when it is crowded, because exits slow down), and the gate limits entry. The forecast runs this forward 40 times with random noise and sudden rushes, so it gives a chance of reaching 4/m² and a bad-case band, not just one line. The controller acts on density now, in 20 minutes, and on that chance. A 0-100 risk score explains what is driving each venue's risk. When real counts arrive, the model corrects its own arrival estimate, and `calibrate.py` can fit venue settings to past data.

**Assumed.** Locations are approximate; areas, gate widths, popularity, visit times and the 2 / 3 / 4 people per m² thresholds are placeholders. Replace them with surveyed values and police guidance. To use your own map, save it as `data/{site.key}.kml`.

**Real counts.** Use the Flask app's `POST /api/telemetry`, or call `engine.get_site("{site.key}").telemetry("V01", count=1800)` from your own sensor code.

This is a decision-support prototype, not a substitute for trained crowd managers and the local authority.""")
