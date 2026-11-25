#!/usr/bin/env python3
"""Download NOAA GEFS-Aerosols PM2.5 and embed it in the map HTML (PM_GEFS block).
Usage: python3 update_gefs.py out.json   (or /path/to/map.html to embed)
Needs: pip install numpy xarray cfgrib eccodes
"""
import sys, os, re, json, tempfile, fcntl, shutil, urllib.request, datetime as dt
import numpy as np, xarray as xr

B = 'https://noaa-gefs-pds.s3.amazonaws.com/'
HTML = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'index.html')
lock = open(os.path.join(tempfile.gettempdir(), 'gefs_update.lock'), 'w')
try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError: sys.exit('another update is running')

def get(u, rng=None, tries=3):
    for i in range(tries):
        try:
            r = urllib.request.Request(u, headers={'Range': rng} if rng else {})
            return urllib.request.urlopen(r, timeout=120).read()
        except Exception:
            if i == tries - 1: raise

def stem(d, h, f): return f'gefs.{d}/{h}/chem/pgrb2ap25/gefs.chem.t{h}z.a2d_0p25.f{f:03d}.grib2'

# 1) latest complete run (f120 exists)
run = None
now = dt.datetime.utcnow()
for back in range(3):
    d = (now - dt.timedelta(days=back)).strftime('%Y%m%d')
    for h in ('18', '12', '06', '00'):
        try: get(B + stem(d, h, 120) + '.idx'); run = (d, h); break
        except Exception: pass
    if run: break
if not run: sys.exit('no GEFS run found')
d, h = run
init = dt.datetime.strptime(d + h, '%Y%m%d%H')
run_s = init.strftime('%Y-%m-%d %H:00 UTC')

JSON_MODE = HTML.endswith('.json')
if JSON_MODE:
    if os.path.exists(HTML) and json.load(open(HTML)).get('run') == run_s: sys.exit('already up to date: ' + run_s)
else:
    src = open(HTML, encoding='utf-8').read()
    if f'run:"{run_s}"' in src: sys.exit('already up to date: ' + run_s)

# 2) fetch only PM2.5 bytes per step
tmp = tempfile.mkdtemp()
fields = []
try:
    for f in range(0, 121, 3):
        s = stem(d, h, f)
        recs = [l.split(':') for l in get(B + s + '.idx').decode().split('\n') if l]
        k = next(i for i, r in enumerate(recs) if len(r) > 7 and r[3] == 'PMTF' and r[4] == 'surface' and '2.5e-06' in r[7])
        a = int(recs[k][1]); b = int(recs[k + 1][1]) - 1
        p = f'{tmp}/f{f}.grib2'
        open(p, 'wb').write(get(B + s, f'bytes={a}-{b}'))
        ds = xr.open_dataset(p, engine='cfgrib', backend_kwargs={'indexpath': ''})
        v = ds[list(ds.data_vars)[0]]
        fields.append(v.values.astype(float)); lat = v.latitude.values; lon = v.longitude.values
        ds.close(); os.remove(p)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
lon = np.where(lon > 180, lon - 360, lon)

# 3) sample grid, hourly interpolation
rows = []
la = 25.4
while la <= 39.5 + 1e-9:
    lo = 44.3
    while lo <= 62 + 1e-9:
        i = int(np.abs(lat - la).argmin()); j = int(np.abs(lon - lo).argmin())
        v = [float(x[i, j]) for x in fields]
        pm = []
        for k in range(121):
            q = min(k // 3, len(v) - 2); w = (k - 3 * q) / 3
            pm.append(round(v[q] + (v[q + 1] - v[q]) * w, 1))
        rows.append({'lat': float(lat[i]), 'lon': float(lon[j]), 'pm': pm})
        lo += 1.15
    la += 1.05
t0 = (init + dt.timedelta(hours=3, minutes=30)).strftime('%Y-%m-%dT%H:00')
if JSON_MODE:
    os.makedirs(os.path.dirname(os.path.abspath(HTML)), exist_ok=True)
    json.dump({'run': run_s, 't0': t0, 'rows': rows}, open(HTML, 'w'), separators=(',', ':'))
    print('updated to', run_s); sys.exit(0)
block = 'const PM_GEFS={run:%s,t0:%s,rows:%s};' % (json.dumps(run_s), json.dumps(t0), json.dumps(rows, separators=(',', ':')))

# 4) replace block atomically
new, n = re.subn(r'const PM_GEFS=\{.*?\};(?=</script>)', lambda m: block, src, count=1, flags=re.S)
if n != 1: sys.exit('PM_GEFS block not found in HTML')
shutil.copy2(HTML, HTML + '.prev')
with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(os.path.abspath(HTML)), encoding='utf-8') as t:
    t.write(new)
os.replace(t.name, HTML)
print('updated to', run_s)
