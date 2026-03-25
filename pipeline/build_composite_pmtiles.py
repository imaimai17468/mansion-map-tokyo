"""
Build composite.pmtiles: 町丁目ごとの立地安全偏差値

1. e-Stat 町丁目境界をダウンロード
2. 既存 choropleth.pmtiles からボーリング統計値を取得
3. flood.pmtiles から洪水データを取得
4. 地盤スコア + 洪水スコア → 総合偏差値を算出
5. tippecanoe で PMTiles に変換
"""

import gzip
import io
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import mapbox_vector_tile
import numpy as np
from pmtiles.reader import MmapSource, Reader

ROOT = Path(__file__).resolve().parent.parent
CHOROPLETH_PATH = ROOT / "public" / "data" / "choropleth.pmtiles"
FLOOD_PATH = ROOT / "public" / "data" / "flood.pmtiles"
LANDPRICE_PATH = ROOT / "public" / "data" / "landprice.pmtiles"
CRIME_PATH = ROOT / "public" / "data" / "crime.pmtiles"
OUTPUT_PATH = ROOT / "public" / "data" / "composite.pmtiles"

ESTAT_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search/data"
    "?dlserveyId=A002005212020&code=13&coordSys=1&format=shape"
    "&downloadType=5&datum=2011"
)


def download_chochome():
    """Download cho-chome boundary Shapefile from e-Stat."""
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
    print(f"  {len(gdf)} cho-chome")
    return gdf


def extract_attributes(pmtiles_path, fields):
    """Extract attributes from a PMTiles file by scanning tiles."""
    print(f"Extracting attributes from {pmtiles_path.name}...")
    records = {}

    with open(pmtiles_path, "rb") as f:
        reader = Reader(MmapSource(f))
        header = reader.header()
        # Scan at zoom 12 (good balance of coverage vs speed)
        z = min(12, header.get("max_zoom", 14))

        for tx in range(3620, 3650):
            for ty in range(1605, 1625):
                tile_data = reader.get(z, tx, ty)
                if tile_data is None:
                    continue
                if tile_data[:2] == b"\x1f\x8b":
                    tile_data = gzip.decompress(tile_data)
                try:
                    decoded = mapbox_vector_tile.decode(tile_data)
                except Exception:
                    continue
                for layer in decoded.values():
                    for feat in layer["features"]:
                        props = feat["properties"]
                        key = f"{props.get('city', '')}_{props.get('area', '')}"
                        if key not in records:
                            records[key] = {f: props.get(f) for f in fields}
                            records[key]["city"] = props.get("city", "")
                            records[key]["area"] = props.get("area", "")

    print(f"  Extracted {len(records)} records")
    return records


def compute_deviation_score(values, invert=False):
    """Compute 偏差値 (mean=50, sd=10). If invert=True, lower raw = higher score."""
    arr = np.array(values, dtype=float)
    valid = ~np.isnan(arr)
    if valid.sum() < 2:
        return np.full_like(arr, 50.0)

    mean = np.nanmean(arr[valid])
    sd = np.nanstd(arr[valid])
    if sd == 0:
        return np.full_like(arr, 50.0)

    scores = 50 + 10 * (arr - mean) / sd
    if invert:
        scores = 100 - scores  # flip: lower raw value = higher score

    return np.clip(scores, 20, 80).round(1)


def main():
    # Step 1: Download cho-chome boundaries
    chochome = download_chochome()

    # Step 2: Extract boring attributes
    boring_data = extract_attributes(
        CHOROPLETH_PATH, ["n50_med", "n50_avg", "cnt"]
    )

    # Step 3: Extract flood attributes
    flood_data = extract_attributes(
        FLOOD_PATH, ["flood_rank", "flood_max"]
    )

    # Step 4: Extract land price attributes
    price_data = extract_attributes(
        LANDPRICE_PATH, ["price_med", "price_cnt"]
    )

    # Step 5: Extract crime attributes
    crime_data = extract_attributes(
        CRIME_PATH, ["crime_total"]
    )

    # Step 6: Join attributes to cho-chome
    chochome["_key"] = chochome["city"] + "_" + chochome["area"]

    # Boring join
    boring_vals = []
    for key in chochome["_key"]:
        rec = boring_data.get(key, {})
        boring_vals.append(rec.get("n50_med"))
    chochome["n50_med"] = boring_vals

    # Flood join
    flood_vals = []
    for key in chochome["_key"]:
        rec = flood_data.get(key, {})
        flood_vals.append(rec.get("flood_rank", 0) or 0)
    chochome["flood_rank"] = flood_vals

    # Land price join
    price_vals = []
    for key in chochome["_key"]:
        rec = price_data.get(key, {})
        price_vals.append(rec.get("price_med"))
    chochome["price_med"] = price_vals

    # Crime join
    crime_vals = []
    for key in chochome["_key"]:
        rec = crime_data.get(key, {})
        crime_vals.append(rec.get("crime_total"))
    chochome["crime_total"] = crime_vals

    # Stats
    has_boring = chochome["n50_med"].notna().sum()
    has_flood = (chochome["flood_rank"] > 0).sum()
    has_price = chochome["price_med"].notna().sum()
    has_crime = chochome["crime_total"].notna().sum()
    print(f"  Matched: {has_boring} boring, {has_flood} flood, {has_price} price, {has_crime} crime")

    # Step 7: Compute 偏差値
    # Ground score: lower n50_med = shallower bedrock = better → invert
    chochome["ground_score"] = compute_deviation_score(
        chochome["n50_med"].fillna(chochome["n50_med"].median()).values,
        invert=True,
    )

    # Flood score: lower flood_rank = less risk = better → invert
    chochome["flood_score"] = compute_deviation_score(
        chochome["flood_rank"].values,
        invert=True,
    )

    # Price score: only for cho-chome with actual price data
    has_price_mask = chochome["price_med"].notna()
    price_scores = np.full(len(chochome), np.nan)
    if has_price_mask.sum() > 1:
        price_scores[has_price_mask] = compute_deviation_score(
            chochome.loc[has_price_mask, "price_med"].values,
            invert=True,
        )
    chochome["price_score"] = price_scores

    # Crime score: lower crime = safer = better → invert
    has_crime_mask = chochome["crime_total"].notna()
    crime_scores = np.full(len(chochome), np.nan)
    if has_crime_mask.sum() > 1:
        crime_scores[has_crime_mask] = compute_deviation_score(
            chochome.loc[has_crime_mask, "crime_total"].values,
            invert=True,
        )
    chochome["crime_score"] = crime_scores

    # Composite: average of available scores
    scores = chochome[["ground_score", "flood_score", "price_score", "crime_score"]]
    chochome["composite"] = scores.mean(axis=1, skipna=True).round(1)

    # Add labels
    chochome["n50_med"] = chochome["n50_med"].round(1)
    chochome["price_med"] = chochome["price_med"].round(0)

    # Replace NaN with 0 for PMTiles output (0 = no data)
    chochome["price_score"] = chochome["price_score"].fillna(0).round(1)
    chochome["crime_score"] = chochome["crime_score"].fillna(0).round(1)

    # Keep only needed columns
    out = chochome[["city", "area", "n50_med", "flood_rank", "price_med", "crime_total",
                     "ground_score", "flood_score", "price_score", "crime_score",
                     "composite", "geometry"]].copy()

    print(f"\n偏差値 stats:")
    print(f"  Ground: mean={out['ground_score'].mean():.1f}, "
          f"min={out['ground_score'].min()}, max={out['ground_score'].max()}")
    print(f"  Flood:  mean={out['flood_score'].mean():.1f}, "
          f"min={out['flood_score'].min()}, max={out['flood_score'].max()}")
    print(f"  Price:  mean={out['price_score'].mean():.1f}, "
          f"min={out['price_score'].min()}, max={out['price_score'].max()}")
    print(f"  Crime:  mean={out['crime_score'].mean():.1f}, "
          f"min={out['crime_score'].min()}, max={out['crime_score'].max()}")
    print(f"  Total:  mean={out['composite'].mean():.1f}, "
          f"min={out['composite'].min()}, max={out['composite'].max()}")

    # Step 6: Export to PMTiles
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
        tmp = f.name
    out.to_file(tmp, driver="GeoJSON")
    print(f"\nWrote temp GeoJSON ({os.path.getsize(tmp) / 1024 / 1024:.1f} MB)")

    subprocess.run(
        [
            "tippecanoe",
            "-o", str(OUTPUT_PATH),
            "-l", "composite",
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
    print(f"Done! {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024 / 1024:.1f} MB)")


if __name__ == "__main__":
    main()
