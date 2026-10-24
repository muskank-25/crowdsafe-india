CrowdSafe India - crowd safety demo for crowded places across India (SAMPLE data, simulated crowds)
https://crowdsafe-india-m2gfhevd78bosash2afq3u.streamlit.app/
1. Install:   python -m pip install -r requirements.txt
2. Run:       streamlit run streamlit_app.py
   (or the other version:  python app.py   then open http://localhost:5000)

Files:
  streamlit_app.py   the Streamlit app (main file for Streamlit Cloud)
  engine.py          the crowd model, forecast, gate controller, routing
  places.py          the list of places and venues (edit this to add your own)
  app.py             Flask web app + API (uses static/index.html)
  static/index.html  page for the Flask version
  requirements.txt   Python packages

All coordinates in places.py are approximate and all sizes are assumed. To use your own map for a place,
save it as data/<place key>.kml (e.g. data/haridwar.kml). Optional numbers in each placemark description:
area=1200 gate=4 pop=1.6 dwell=25

Model improvements (v2):
  - Risk score 0-100 per venue with reasons (density now and soon, trend, queue, inflow vs outflow, alerts)
  - Monte Carlo forecast: chance of reaching 4/m2 and a bad-case band, not just one line
  - Gates react early to that chance, not only to current density
  - Congestion: crowded venues empty more slowly
  - Self-correcting: real counts sent to /api/telemetry adjust the arrival estimate and flag sudden jumps
  - calibrate.py fits venue settings to real history:  python calibrate.py haridwar sample_history.csv

Voice alerts (v3):
  - Events: venue becomes crowded / critical (repeats every 60 s while critical), gate closed or one-in-one-out,
    citizen alert raised, sudden jump in counts, back to safe. Messages in English, Hindi and Bengali.
  - Flask page: tick "Voice alerts" (speaks in the browser, siren beep first; needs a voice installed for Hindi/Bengali).
  - Streamlit: turn on "Spoken alerts" in the sidebar. Needs internet for the spoken voice (gTTS); offline it plays a siren.
  - API: GET /api/events?site=<key>&since=<number>&lang=en|hi|bn
