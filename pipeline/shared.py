"""Shared utilities for pipeline scripts."""

import io
import re
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd

ESTAT_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search/data"
    "?dlserveyId=A002005212020&code=13&coordSys=1&format=shape"
    "&downloadType=5&datum=2011"
)

KANJI_TO_DIGIT = str.maketrans("一二三四五六七八九", "123456789")


def normalize(s: str) -> str:
    """Normalize string: fullwidth → halfwidth, kanji digits → ascii."""
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s = s.translate(KANJI_TO_DIGIT)
    return s


def strip_chome(area: str) -> str:
    """Remove chome number: '丸の内1丁目' → '丸の内'."""
    return re.sub(r"\d+丁目$", "", normalize(area))


def download_oaza() -> gpd.GeoDataFrame:
    """Download cho-chome boundaries from e-Stat and dissolve to oaza (大字・町) level."""
    print("Downloading cho-chome boundaries from e-Stat...")
    req = Request(ESTAT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=120) as resp:
        zip_data = resp.read()
    print(f"  Downloaded {len(zip_data) / 1024 / 1024:.1f} MB")

    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        zf.extractall(tmpdir)

    shp_files = list(Path(tmpdir).rglob("*.shp"))
    gdf = gpd.read_file(shp_files[0])
    gdf = gdf.rename(columns={"CITY_NAME": "city", "S_NAME": "area"})
    gdf = gdf[gdf["area"].notna() & (gdf["area"] != "")].copy()
    gdf = gdf.to_crs("EPSG:4326")
    print(f"  {len(gdf)} cho-chome (丁目)")

    # Dissolve to oaza level
    gdf["oaza"] = gdf["area"].apply(strip_chome)
    dissolved = gdf.dissolve(by=["city", "oaza"], as_index=False)
    dissolved = dissolved[["city", "oaza", "geometry"]].copy()
    dissolved = dissolved.rename(columns={"oaza": "area"})
    # Fix any invalid geometries from dissolve
    dissolved["geometry"] = dissolved["geometry"].buffer(0)
    print(f"  → {len(dissolved)} oaza (大字・町) after dissolve")

    return dissolved
