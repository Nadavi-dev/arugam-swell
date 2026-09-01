# arugam-swell

Matches the Arugam Bay swell forecast to a real Sentinel-2 satellite frame of a comparable
past day, and publishes the result to GitHub Pages. Rebuilds twice daily.

It does not judge waves. It finds you a photograph and stops.

## How it works

1. **Sample upstream.** Swell is read at 5.20N 81.00E — deep water south of Sri Lanka, before
   the coast refracts it. The grid point at Arugam itself is shadowed by the island and
   under-reads every event.
2. **Match to a frame.** `lib.json` holds 31 cloud-free Sentinel-2 frames of this coast
   (2022–2026), each tagged with the swell that was running when the shutter opened. Each
   forecast day is matched to its nearest neighbour by weighted distance over six terms:
   offshore and local swell height, period and direction.
3. **Render.** `template.html` is filled between the `FORECAST:START` / `FORECAST:END`
   markers and written to `site/`.

## Two things that will bite you if you fork this

**Scene cloud cover is not coastal cloud cover.** Sentinel-2's `eo:cloud_cover` covers a
110 km tile that is mostly inland. Recompute it from the SCL band over the coastal strip
alone. 2023-07-21 reads 15.8% on the tile and 0.3% on the coast; 2026-06-30 reads 10.6% on
the tile and 28.6% on the coast.

**Never match across wave models.** The library's swell tags and the incoming forecast must
come from the same model. ECMWF and WaveWatch III described one morning as 1.78 m @ 11.95 s
from 194° and 1.38 m @ 15.15 s from 207° — the same wave, three seconds apart. Crossing them
returns a confident wrong answer. This repo uses `ncep_gfswave025` on both sides.

## Files

| | |
|---|---|
| `build.py` | fetch, match, render — standard library only, no API keys |
| `lib.json` | 31 frames + 101 percentile breakpoints for this coast |
| `template.html` | the page, with the refreshable block marked |
| `*.b64` | the satellite frames, base64 so they survive text-only transport |
| `.github/workflows/refresh.yml` | cron 00:30 and 14:30 UTC = 06:00 and 20:00 Asia/Colombo |

## Porting to another break

Four things are site-specific: the upstream sample point, the coastal window the cloud test
runs over, the MGRS tile and its overpass hour, and the offshore wind bearing. Everything
else is identical for any coast on Earth.

## Sources

Sentinel-2 L2A (ESA/Copernicus) via AWS Open Data `sentinel-cogs` · scene catalogue from
Element84 Earth Search STAC · forecasts from Open-Meteo (NOAA WaveWatch III and ECMWF).
All free, no keys.
