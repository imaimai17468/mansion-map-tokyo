"""
Build crime.pmtiles: 町丁目ごとの犯罪認知件数

1. e-Stat から町丁目境界をダウンロード
2. 警視庁 町丁別認知件数 CSV をダウンロード
3. 町丁目名で結合
4. tippecanoe で PMTiles に変換
"""

import io
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "public" / "data" / "crime.pmtiles"

ESTAT_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search/data"
    "?dlserveyId=A002005212020&code=13&coordSys=1&format=shape"
    "&downloadType=5&datum=2011"
)

# 警視庁 R7 (2025年) 町丁別認知件数
CRIME_URL = (
    "https://www.keishicho.metro.tokyo.lg.jp/"
    "about_mpd/jokyo_tokei/jokyo/ninchikensu.files/R7.csv"
)


KANJI_TO_DIGIT = str.maketrans("一二三四五六七八九", "123456789")


def normalize(s: str) -> str:
    """Normalize string: fullwidth → halfwidth, kanji digits → ascii, strip whitespace."""
    s = unicodedata.normalize("NFKC", s).strip()
    s = s.translate(KANJI_TO_DIGIT)
    return s


def parse_location(raw: str) -> tuple[str, str]:
    """Parse '千代田区飯田橋1丁目' into ('千代田区', '飯田橋1丁目')."""
    s = normalize(raw)
    # Match ward (区), city (市), or gun+town (郡...町/村)
    m = re.match(r"^(.+?[区市])(.+)$", s)
    if m:
        return m.group(1), m.group(2)
    # Gun area: 西多摩郡瑞穂町大字石畑
    m = re.match(r"^(.+?郡.+?[町村])(.+)$", s)
    if m:
        return m.group(1), m.group(2)
    return s, ""


def download_chochome():
    """Download cho-chome boundaries from e-Stat."""
    print("Downloading cho-chome boundaries from e-Stat...")
    req = Request(ESTAT_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=120) as resp:
        zip_data = resp.read()

    tmpdir = tempfile.mkdtemp()
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        zf.extractall(tmpdir)

    shp_files = list(Path(tmpdir).rglob("*.shp"))
    gdf = gpd.read_file(shp_files[0])
    gdf = gdf.rename(columns={"CITY_NAME": "city", "S_NAME": "area"})
    gdf = gdf[gdf["area"].notna() & (gdf["area"] != "")].copy()
    gdf = gdf.to_crs("EPSG:4326")
    # Normalize names for matching
    gdf["city_norm"] = gdf["city"].apply(normalize)
    gdf["area_norm"] = gdf["area"].apply(normalize)
    print(f"  {len(gdf)} cho-chome")
    return gdf


def download_crime():
    """Download crime CSV from 警視庁."""
    print(f"Downloading {CRIME_URL}...")
    req = Request(CRIME_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=60) as resp:
        raw = resp.read()

    df = pd.read_csv(io.BytesIO(raw), encoding="cp932")
    print(f"  {len(df)} rows, columns: {list(df.columns[:5])}...")

    location_col = df.columns[0]  # 市区町丁
    total_col = df.columns[1]     # 総合計

    # Filter out summary rows
    summary_patterns = ["計", "不明", "他県", "海外"]
    mask = ~df[location_col].astype(str).apply(
        lambda x: any(p in x for p in summary_patterns)
    )
    df = df[mask].copy()

    # Parse location
    parsed = df[location_col].astype(str).apply(parse_location)
    df["city"] = [p[0] for p in parsed]
    df["area"] = [p[1] for p in parsed]
    df["crime_total"] = pd.to_numeric(df[total_col], errors="coerce").fillna(0).astype(int)

    # Extract key crime categories
    cols = list(df.columns)
    crime_cols = {}
    for col in cols:
        if "凶悪犯計" in str(col):
            crime_cols["crime_violent"] = col
        elif "粗暴犯計" in str(col):
            crime_cols["crime_assault"] = col
        elif "侵入窃盗計" in str(col):
            crime_cols["crime_burglary"] = col
        elif "非侵入窃盗計" in str(col):
            crime_cols["crime_theft"] = col

    for new_name, old_col in crime_cols.items():
        df[new_name] = pd.to_numeric(df[old_col], errors="coerce").fillna(0).astype(int)

    df = df[df["area"] != ""].copy()
    print(f"  {len(df)} cho-chome records after filtering")
    print(f"  Total crimes: {df['crime_total'].sum():,}")
    return df


def join_crime(chochome_gdf, crime_df):
    """Join crime data to cho-chome by name matching."""
    print("Joining by name...")

    # Build crime lookup
    crime_lookup = {}
    for _, row in crime_df.iterrows():
        key = normalize(row["city"]) + "_" + normalize(row["area"])
        crime_lookup[key] = {
            "crime_total": row["crime_total"],
            "crime_violent": row.get("crime_violent", 0),
            "crime_assault": row.get("crime_assault", 0),
            "crime_burglary": row.get("crime_burglary", 0),
            "crime_theft": row.get("crime_theft", 0),
        }

    # Match
    matched = 0
    records = []
    for _, row in chochome_gdf.iterrows():
        key = row["city_norm"] + "_" + row["area_norm"]
        crime = crime_lookup.get(key, {})
        if crime:
            matched += 1
        records.append({
            "crime_total": crime.get("crime_total", 0),
            "crime_violent": crime.get("crime_violent", 0),
            "crime_assault": crime.get("crime_assault", 0),
            "crime_burglary": crime.get("crime_burglary", 0),
            "crime_theft": crime.get("crime_theft", 0),
        })

    for col in ["crime_total", "crime_violent", "crime_assault", "crime_burglary", "crime_theft"]:
        chochome_gdf[col] = [r[col] for r in records]

    has_crime = (chochome_gdf["crime_total"] > 0).sum()
    print(f"  Name matched: {matched}/{len(chochome_gdf)}")
    print(f"  With crimes > 0: {has_crime}")

    out = chochome_gdf[["city", "area", "crime_total", "crime_violent",
                         "crime_assault", "crime_burglary", "crime_theft",
                         "geometry"]].copy()
    return out


def to_pmtiles(gdf, output_path):
    """Export GeoDataFrame to PMTiles via tippecanoe."""
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
        tmp = f.name
    gdf.to_file(tmp, driver="GeoJSON")
    print(f"Wrote temp GeoJSON ({os.path.getsize(tmp) / 1024 / 1024:.1f} MB)")

    subprocess.run(
        [
            "tippecanoe",
            "-o", str(output_path),
            "-l", "crime",
            "--force",
            "--no-feature-limit",
            "--no-tile-size-limit",
            "--minimum-zoom=8",
            "--maximum-zoom=14",
            "--coalesce-densest-as-needed",
            tmp,
        ],
        check=True,
    )
    os.unlink(tmp)
    print(f"Done! {output_path} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")


def main():
    chochome = download_chochome()
    crime = download_crime()
    result = join_crime(chochome, crime)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
