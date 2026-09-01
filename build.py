#!/usr/bin/env python3
"""Arugam swell window - fetch forecast, match a satellite frame to each day, render site/.
Standard library only. No API keys."""
import json, math, os, sys, time, urllib.request, urllib.parse
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
HE_FULL = ("שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון")


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
    link = " has-frame" if d.get("img") else ""
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


def hero_html(d, frames_by_date, today):
    cls, lab = chip(d["pct"])
    when = "הבוקר" if d["date"] == today else ("מחר בבוקר" if d["lead"] == 1 else f'בעוד {d["lead"]} ימים')
    f = frames_by_date[d["an"]]
    if d["eh"] is not None:
        cross = (f'<span class="cmp" dir="ltr">WW3 {d["h"]:.2f}m / {d["t"]:.1f}s</span>'
                 f'<span class="cmp" dir="ltr">ECMWF {d["eh"]:.2f}m / {d["et"]:.1f}s</span>')
    else:
        cross = ('<span class="cmp" dir="ltr">WW3 %.2fm / %.1fs</span>'
                 '<span class="cmp solo">מודל אחד בלבד — אין הצלבה</span>') % (d["h"], d["t"])
    img = (f'<img src="img/{d["an"]}.jpg" alt="Sentinel-2, ארוגם ביי, {d["an"]}">'
           if d.get("img") else
           '<p class="h-none">הפריים התואם לא נרנדר בריצה הזאת.</p>')
    return f'''<div class="hero {cls}">
<div class="h-top"><p class="h-lab">{when} · {lab}</p>
<h2 class="h-day">{HE_FULL[datetime.strptime(d["date"],"%Y-%m-%d").weekday()]}<small>{d["dm"]}</small></h2></div>
<div class="h-nums">
<div class="h-n"><b>{d["h"]:.2f}</b><i>גובה (מ׳)</i></div>
<div class="h-n per"><b>{d["t"]:.1f}</b><i>מחזור (ש׳)</i></div>
<div class="h-n"><b>{d["dr"]:.0f}&deg;</b><i>כיוון</i></div>
<div class="h-n"><b>{d["ws"]:.0f}</b><i>רוח (kn)</i></div>
<div class="h-n"><b>{d["pct"]}</b><i>אחוזון</i></div>
</div>
<div class="h-cross">{cross}</div>
{img}
<p class="h-cap">היום הדומה ביותר בארכיון: <b>{d["an"]}</b> — {f["h"]:.2f}מ׳ @ {f["t"]:.1f}ש׳ מ-{f["dr"]:.0f}&deg;, עננות {f["c"]}%. מרחק התאמה {d["dist"]:.2f}.</p>
</div>'''


def frames_html(days, frames_by_date):
    seen, out = set(), []
    for d in days:
        if d["an"] in seen or not d.get("img"):
            continue
        seen.add(d["an"])
        f = frames_by_date[d["an"]]
        used = [x["dm"] for x in days if x["an"] == d["an"]]
        out.append(f'''<figure class="frame" id="f{d["an"]}">
<div class="f-head"><h3>{d["an"]}</h3><code dir="ltr">{f["h"]:.2f}m @ {f["t"]:.1f}s &middot; {f["dr"]:.0f}&deg;</code></div>
<img src="img/{d["an"]}.jpg" alt="Sentinel-2, ארוגם ביי, {d["an"]}" loading="lazy">
<figcaption>האנלוג של {", ".join(used)}. עננות מעל החוף {f["c"]}%.</figcaption></figure>''')
    return "".join(out)


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
        best, bd = match(rec, frames)
        rec["an"], rec["dist"], rec["date"] = best["d"], bd, day
        days.append(rec)

    if not days:
        raise SystemExit("FATAL: forecast produced no usable days")

    frames_by_date = {f["d"]: f for f in frames}

    # the hero is the next morning still ahead of us: today before 10:00, else tomorrow
    now = datetime.now(LKT)
    today = now.strftime("%Y-%m-%d")
    upcoming = [d for d in days if d["date"] > today or (d["date"] == today and now.hour < 10)]
    hero = upcoming[0] if upcoming else days[0]

    # render only the frames actually referenced, hero first so it is never the one that fails
    os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
    wanted, rendered = [hero["an"]] + [d["an"] for d in days], {}
    try:
        import render as _render
    except Exception as e:
        print("WARN: renderer unavailable:", e); _render = None
    for date in dict.fromkeys(wanted):
        if _render is None:
            break
        dest = os.path.join(OUT, "img", date + ".jpg")
        if os.path.exists(dest) and os.path.getsize(dest) > 10000:
            rendered[date] = True
            print(f"  cached   {date}", flush=True)
            continue
        try:
            t0 = time.time()
            _render.frame(frames_by_date[date]["id"], dest)
            rendered[date] = True
            print(f"  rendered {date} in {time.time()-t0:.0f}s", flush=True)
        except Exception as e:
            print(f"  WARN {date}: {e}", flush=True)
    for d in days:
        d["img"] = d["an"] in rendered
    hero["img"] = hero["an"] in rendered

    stamp = datetime.now(LKT).strftime("%d %b %Y %H:%M")
    html = open(os.path.join(ROOT, "template.html"), encoding="utf-8").read()
    html = html.replace("{{STAMP}}", f'<p class="stamp">updated {stamp} LKT</p>')
    html = html.replace("{{ROWS}}", '<div class="days">' + "".join(row(d) for d in days) + '</div>')
    html = html.replace("{{HERO}}", hero_html(hero, frames_by_date, today))
    html = html.replace("{{FRAMES}}", frames_html(days, frames_by_date))

    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    peak = max(days, key=lambda d: d["pct"])
    print(f"{len(days)} days | {len(rendered)} frames rendered | "
          f"hero {hero['dm']} p{hero['pct']} -> {hero['an']} (d={hero['dist']:.2f}) | "
          f"peak {peak['dm']} {peak['h']:.2f}m {peak['t']:.1f}s p{peak['pct']}")


if __name__ == "__main__":
    main()
