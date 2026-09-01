#!/usr/bin/env python3
"""Arugam swell window - fetch forecast, match a satellite frame to each day, render site/.
Standard library only. No API keys."""
import json, math, base64, os, sys, time, urllib.request, urllib.parse
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.join(ROOT, "site")
LKT  = timezone(timedelta(hours=5, minutes=30))          # Asia/Colombo

OFFSHORE = (5.20, 81.00)     # deep water S of Sri Lanka - swell before it refracts
LOCAL    = (6.84, 81.84)     # Arugam Bay
MORNING  = ("06:00", "07:00", "08:00", "09:00", "10:00")

MARINE = "https://marine-api.open-meteo.com/v1/marine"
WEATH  = "https://api.open-meteo.com/v1/forecast"
HOURLY = "swell_wave_height,swell_wave_period,swell_wave_direction"


def fetch(base, params, tries=4):
    url = base + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise SystemExit(f"FATAL fetch failed: {base} :: {last}")


def marine(lat, lon, model=None):
    p = {"latitude": lat, "longitude": lon, "hourly": HOURLY,
         "forecast_days": 16, "timezone": "Asia/Colombo"}
    if model:
        p["models"] = model
    return fetch(MARINE, p)["hourly"]


def index(h):
    """time -> {var: value}, tolerating the model suffix open-meteo appends."""
    keys = [k for k in h if k != "time"]
    out = {}
    for i, t in enumerate(h["time"]):
        out[t] = {k.split("_ncep")[0]: h[k][i] for k in keys}
    return out


def morning_mean(src, day, field):
    vals = [src[f"{day}T{hh}"][field] for hh in MORNING
            if f"{day}T{hh}" in src and src[f"{day}T{hh}"].get(field) is not None]
    return sum(vals) / len(vals) if vals else None


def angdiff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


W = dict(h=0.30, t=1.50, d=12.0, lh=0.20, lt=1.50, ld=10.0)

def match(day, frames):
    best, bd = None, 1e9
    for f in frames:
        s = math.sqrt(
            ((day["h"]  - f["h"])  / W["h"])  ** 2 +
            ((day["t"]  - f["t"])  / W["t"])  ** 2 +
            (angdiff(day["dr"], f["dr"])      / W["d"])  ** 2 +
            ((day["lh"] - f["lh"]) / W["lh"]) ** 2 +
            ((day["lt"] - f["lt"]) / W["lt"]) ** 2 +
            (angdiff(day["ldr"], f["ldr"])    / W["ld"]) ** 2)
        if s < bd:
            best, bd = f, s
    return best, bd


HE_DOW = ("ב׳", "ג׳", "ד׳", "ה׳", "ו׳", "ש׳", "א׳")   # Python weekday(): Mon=0 .. Sun=6
FRAME_IMAGES = {"2026-08-31", "2026-08-19", "2024-08-09"}


def chip(p):
    if p >= 80: return "go", "לך"
    if p >= 60: return "ok", "עובד"
    if p >= 40: return "fade", "דועך"
    return "flat", "שטוח"


def row(d):
    cls, lab = chip(d["pct"])
    if d["eh"] is not None:
        ecm, solo = f'ECMWF {d["eh"]:.2f}m / {d["et"]:.1f}s', ""
    else:
        ecm, solo = "WW3 בלבד — אין הצלבה", " solo"
    off = " off" if 200 <= d["wd"] <= 300 else ""
    link = " has-frame" if d["an"] in FRAME_IMAGES else ""
    return (
        f'<button class="day {cls}{link}" data-analog="{d["an"]}">'
        f'<span class="d-when"><b>{d["dow"]}</b><i dir="ltr">{d["dm"]}</i></span>'
        f'<span class="d-bar"><span class="d-fill" style="--p:{d["pct"]}%"></span></span>'
        f'<span class="d-num" dir="ltr"><b>{d["h"]:.2f}</b><i>m</i></span>'
        f'<span class="d-num per" dir="ltr"><b>{d["t"]:.1f}</b><i>s</i></span>'
        f'<span class="d-num" dir="ltr"><b>{d["dr"]:.0f}</b><i>&deg;</i></span>'
        f'<span class="d-wind{off}" dir="ltr">{d["ws"]:.0f} kn</span>'
        f'<span class="d-chip">{lab}</span>'
        f'<span class="d-meta"><span class="cmp{solo}" dir="ltr">{ecm}</span>'
        f'<span class="cmp" dir="ltr">+{d["lead"]}d</span>'
        f'<span class="cmp" dir="ltr">&asymp; {d["an"]}</span></span></button>')


def main():
    lib     = json.load(open(os.path.join(ROOT, "lib.json"), encoding="utf-8"))
    breaks  = lib["pctBreaks"]
    frames  = lib["frames"]
    for f in frames:                       # normalise key names used by match()
        f.setdefault("ldr", f.get("ldr"))

    ww3_off = index(marine(*OFFSHORE, model="ncep_gfswave025"))
    ww3_loc = index(marine(*LOCAL,    model="ncep_gfswave025"))
    ecmwf   = index(marine(*OFFSHORE))
    wind    = index(fetch(WEATH, {"latitude": LOCAL[0], "longitude": LOCAL[1],
                                  "hourly": "wind_speed_10m,wind_direction_10m",
                                  "forecast_days": 16, "wind_speed_unit": "kn",
                                  "timezone": "Asia/Colombo"})["hourly"])

    today = datetime.now(LKT).date()
    days  = []
    for day in sorted({t[:10] for t in ww3_off}):
        g = lambda src, f: morning_mean(src, day, f)
        h, t, dr = (g(ww3_off, "swell_wave_height"), g(ww3_off, "swell_wave_period"),
                    g(ww3_off, "swell_wave_direction"))
        lh, lt, ldr = (g(ww3_loc, "swell_wave_height"), g(ww3_loc, "swell_wave_period"),
                       g(ww3_loc, "swell_wave_direction"))
        ws, wd = g(wind, "wind_speed_10m"), g(wind, "wind_direction_10m")
        if None in (h, t, dr, lh, lt, ldr, ws, wd):
            continue
        e = h * h * t
        pct = 0
        for i, b in enumerate(breaks):
            if b <= e:
                pct = i
        dd = datetime.strptime(day, "%Y-%m-%d").date()
        rec = dict(h=h, t=t, dr=dr, lh=lh, lt=lt, ldr=ldr, ws=ws, wd=wd, pct=pct,
                   eh=g(ecmwf, "swell_wave_height"), et=g(ecmwf, "swell_wave_period"),
                   dow=HE_DOW[dd.weekday()], dm=dd.strftime("%d %b"),
                   lead=(dd - today).days)
        best, _ = match(rec, frames)
        rec["an"] = best["d"]
        days.append(rec)

    if not days:
        raise SystemExit("FATAL: forecast produced no usable days")

    stamp = datetime.now(LKT).strftime("%d %b %Y %H:%M")
    html = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    html = html.replace("{{STAMP}}", f'<p class="stamp">updated {stamp} LKT</p>')
    html = html.replace("{{ROWS}}", '<div class="days">' + "".join(row(d) for d in days) + '</div>')

    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    for name in os.listdir(ROOT):
        if name.endswith(".b64"):
            raw = base64.b64decode("".join(
                open(os.path.join(ROOT, name), encoding="ascii").read().split()))
            open(os.path.join(OUT, "img", name[:-4] + ".jpg"), "wb").write(raw)
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    peak = max(days, key=lambda d: d["pct"])
    print(f"{len(days)} days | peak {peak['dm']} {peak['h']:.2f}m {peak['t']:.1f}s "
          f"{peak['dr']:.0f}deg p{peak['pct']} | analog {peak['an']}")


if __name__ == "__main__":
    main()
