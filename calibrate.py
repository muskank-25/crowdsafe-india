"""Fit venue settings (popularity and visit time) to REAL past counts, so forecasts match what really happens.
Usage:   python calibrate.py <place key> <history.csv>        e.g.  python calibrate.py haridwar sample_history.csv
CSV columns:  venue_id,hour,count[,day]     (hour 0-24 as a number like 18.5; day = an occasion name from places.py, optional)
Need at least 4 readings per venue from one day. Results are saved to data/<place key>_calibration.json and used automatically on the next start.
"""
import csv, sys
import engine

if len(sys.argv) != 3: sys.exit(__doc__)
site = engine.get_site(sys.argv[1])
res = site.calibrate(list(csv.DictReader(open(sys.argv[2]))))
if not res: sys.exit("No venue had 4+ readings on the same day. Check the column names and venue ids.")
print(f"{'venue':8}{'pop':>6}{'dwell':>7}{'error before':>14}{'error after':>13}   (error = average people/m2 off)")
for vid, r in res.items(): print(f"{vid:8}{r['pop']:>6}{r['dwell']:>7}{r['mae_before']:>14}{r['mae_after']:>13}")
print("Saved. Restart the app to use the fitted values.")
