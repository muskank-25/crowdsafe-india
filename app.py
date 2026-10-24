"""CrowdSafe India - Flask web app (map dashboard + JSON API). The crowd model lives in engine.py.
Run:  python -m pip install -r requirements.txt && python app.py   ->  http://localhost:5000
Every API call takes ?site=<key> (GET) or {"site": "<key>"} in the JSON body (POST); see /api/sites for the keys.
"""
import os
from flask import Flask, jsonify, request, send_from_directory
import engine

app = Flask(__name__, static_folder=os.path.join(engine.BASE, "static"))

def S():
    j = request.get_json(silent=True) if request.method == "POST" else None
    return engine.get_site(request.args.get("site") or (j or {}).get("site"))

def body(): return request.get_json(silent=True) or {}

@app.get("/api/sites")
def sites(): return jsonify(sites=engine.site_list(), default=engine.DEFAULT)

@app.get("/api/venues")
def venues():
    s = S(); s.tick(); return jsonify(s.snapshot())

@app.get("/api/events")          # ?since=<seq>&lang=en|hi|bn  - new alert events with text for voice; without since returns only the latest seq
def events():
    s = S(); s.tick(); return jsonify(s.events_since(request.args.get("since"), request.args.get("lang", "en")))

@app.get("/api/plan")
def plan():
    s = S(); s.tick(); return jsonify(s.plan_core())

@app.post("/api/apply")
def apply_plan(): return jsonify(ok=True, changed=S().apply_plan())

@app.get("/api/forecast")
def forecast():
    s = S(); s.tick(); return jsonify(s.forecast())

@app.get("/api/route")
def route():
    s = S(); s.tick()
    return jsonify(s.route_core(float(request.args["lat"]), float(request.args["lon"]), int(request.args.get("n", 4))))

@app.post("/api/telemetry")      # {"site":"haridwar","venue_id":"V01","count":1800} or {"venue_id":"V01","density":3.2,"queue":400}
def telemetry():
    j = body(); return jsonify(ok=S().telemetry(j.get("venue_id"), j.get("count"), j.get("density"), j.get("queue")))

@app.post("/api/report")         # citizen / steward alert: crush risk, blocked exit, panic, medical emergency
def report():
    j = body(); ok = S().report(j.get("venue_id"), j.get("type", "crush risk"))
    return (jsonify(ok=True) if ok else (jsonify(error="unknown venue"), 404))

@app.post("/api/clear_alert")
def clear_alert():
    S().clear_alerts(set(body().get("ids", []))); return jsonify(ok=True)

@app.post("/api/scenario")       # demo: {"venue_id":"V03","surge":0.6} | {"day":"..."} | {"auto":true} | {"hour":20}
def scenario():
    j = body(); S().scenario(j.get("day"), j.get("auto"), j.get("hour"), j.get("venue_id"), j.get("surge"), j.get("speed")); return jsonify(ok=True)

@app.post("/api/reset")
def reset():
    S().reset(); return jsonify(ok=True)

@app.get("/")
def index(): return send_from_directory(app.static_folder, "index.html")

if __name__ == "__main__": app.run(debug=False, port=5000)
