"""Render one Sentinel-2 frame of the Arugam Bay coast as a true-colour JPEG.
Reads windowed COGs straight off AWS Open Data - no download of the full scene."""
import os
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
import numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from PIL import Image

BUCKET = "https://sentinel-cogs.s3.us-west-2.amazonaws.com/sentinel-s2-l2a-cogs/44/N/NN"
AOI    = (81.740, 6.630, 81.900, 6.970)      # Whiskey Point -> Okanda
WIDTH  = 1200                                 # output width in px


def _cog(scene_id, band):
    y, m = scene_id.split("_")[2][:4], str(int(scene_id.split("_")[2][4:6]))
    return f"{BUCKET}/{y}/{m}/{scene_id}/{band}.tif"


def _read(scene_id, band, count=1):
    with rasterio.open(_cog(scene_id, band)) as src:
        b = transform_bounds("EPSG:4326", src.crs, *AOI)
        w = from_bounds(*b, transform=src.transform)
        idx = [1, 2, 3] if count == 3 else 1
        a = src.read(indexes=idx, window=w).astype(np.float32)
    return a


def frame(scene_id, out_path):
    """ESA's true-colour product, levelled so the sea keeps its swell lines."""
    rgb = np.moveaxis(_read(scene_id, "TCI", 3), 0, -1) / 255.0
    nir = _read(scene_id, "B08") * 1e-4 - 0.1
    water = nir < 0.055

    lum  = rgb.mean(2, keepdims=True)
    land = np.clip(np.power(np.clip(rgb * 1.35, 0, 1), 0.88), 0, 1)
    land = np.clip(lum + (land - lum) * 1.25, 0, 1)

    if water.any():
        sea_px = rgb[water]
        lo = np.percentile(sea_px, 0.5, axis=0)
        hi = np.percentile(sea_px, 99.8, axis=0)
        sea = np.power(np.clip((rgb - lo) / np.maximum(hi - lo, 1e-3), 0, 1), 0.80)
        slum = sea.mean(2, keepdims=True)
        sea = np.clip(slum + (sea - slum) * 0.85, 0, 1)
    else:
        sea = rgb

    out = np.where(water[..., None], sea, land)
    im = Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8))
    im = im.resize((WIDTH, int(im.height * WIDTH / im.width)), Image.LANCZOS)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    im.save(out_path, "JPEG", quality=80, optimize=True, progressive=True)
    return out_path
