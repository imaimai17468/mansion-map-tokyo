"""
Build composite.pmtiles: 町丁目ごとの立地安全偏差値

1. e-Stat 町丁目境界をダウンロード
2. 既存 choropleth.pmtiles からボーリング統計値を取得
3. flood.pmtiles から洪水データを取得
4. 地盤スコア + 洪水スコア → 総合偏差値を算出
5. tippecanoe で PMTiles に変換
"""

import gzip
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import mapbox_vector_tile
import numpy as np
from pmtiles.reader import MmapSource, Reader

from shared import download_oaza, strip_chome

ROOT = Path(__file__).resolve().parent.parent
CHOROPLETH_PATH = ROOT / "public" / "data" / "choropleth.pmtiles"
FLOOD_PATH = ROOT / "public" / "data" / "flood.pmtiles"
LANDPRICE_PATH = ROOT / "public" / "data" / "landprice.pmtiles"
CRIME_PATH = ROOT / "public" / "data" / "crime.pmtiles"
LIQUEFACTION_PATH = ROOT / "public" / "data" / "liquefaction.pmtiles"
ACCESS_PATH = ROOT / "public" / "data" / "access.pmtiles"
MANSION_PATH = ROOT / "public" / "data" / "mansion.pmtiles"
SHOPS_PATH = ROOT / "public" / "data" / "shops.pmtiles"
MEDICAL_PATH = ROOT / "public" / "data" / "medical.pmtiles"
OUTPUT_PATH = ROOT / "public" / "data" / "composite.pmtiles"


def extract_attributes(pmtiles_path, fields):
    """Extract attributes from a PMTiles file by scanning tiles.

    Keys are normalized to oaza level using strip_chome so they match the
    oaza-level boundaries produced by download_oaza().
    """
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
                        city = props.get("city", "")
                        area = props.get("area", "")
                        key = f"{city}_{strip_chome(area)}"
                        if key not in records:
                            records[key] = {f: props.get(f) for f in fields}
                            records[key]["city"] = city
                            records[key]["area"] = area

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
    # Step 1: Download oaza boundaries
    oaza = download_oaza()

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

    # Step 6: Extract liquefaction attributes
    liq_data = extract_attributes(
        LIQUEFACTION_PATH, ["liq_max", "liq_cnt"]
    )

    # Step 7: Extract access attributes
    access_data = extract_attributes(
        ACCESS_PATH, ["access_index", "nearest_station"]
    )

    # Step 8: Extract mansion price attributes
    mansion_data = extract_attributes(
        MANSION_PATH, ["mansion_price_tsubo", "mansion_cnt"]
    )

    # Step 9: Extract shops attributes
    shops_data = extract_attributes(
        SHOPS_PATH, ["shop_total"]
    )

    # Step 10: Extract medical attributes
    medical_data = extract_attributes(
        MEDICAL_PATH, ["medical_total"]
    )

    # Step 11: Join attributes to oaza (use strip_chome for key matching)
    oaza["_key"] = oaza.apply(
        lambda r: r["city"] + "_" + strip_chome(r["area"]), axis=1
    )

    # Boring join
    boring_vals = []
    for key in oaza["_key"]:
        rec = boring_data.get(key, {})
        boring_vals.append(rec.get("n50_med"))
    oaza["n50_med"] = boring_vals

    # Flood join
    flood_vals = []
    for key in oaza["_key"]:
        rec = flood_data.get(key, {})
        flood_vals.append(rec.get("flood_rank", 0) or 0)
    oaza["flood_rank"] = flood_vals

    # Land price join
    price_vals = []
    for key in oaza["_key"]:
        rec = price_data.get(key, {})
        price_vals.append(rec.get("price_med"))
    oaza["price_med"] = price_vals

    # Crime join
    crime_vals = []
    for key in oaza["_key"]:
        rec = crime_data.get(key, {})
        crime_vals.append(rec.get("crime_total"))
    oaza["crime_total"] = crime_vals

    # Liquefaction join
    liq_vals = []
    for key in oaza["_key"]:
        rec = liq_data.get(key, {})
        liq_vals.append(rec.get("liq_max"))
    oaza["liq_max"] = liq_vals

    # Access join
    access_vals = []
    for key in oaza["_key"]:
        rec = access_data.get(key, {})
        access_vals.append(rec.get("access_index"))
    oaza["access_index"] = access_vals

    # Mansion price join
    mansion_vals = []
    for key in oaza["_key"]:
        rec = mansion_data.get(key, {})
        mansion_vals.append(rec.get("mansion_price_tsubo"))
    oaza["mansion_price_tsubo"] = mansion_vals

    # Shops join
    shops_vals = []
    for key in oaza["_key"]:
        rec = shops_data.get(key, {})
        shops_vals.append(rec.get("shop_total"))
    oaza["shop_total"] = shops_vals

    # Medical join
    medical_vals = []
    for key in oaza["_key"]:
        rec = medical_data.get(key, {})
        medical_vals.append(rec.get("medical_total"))
    oaza["medical_total"] = medical_vals

    # Stats
    has_boring = oaza["n50_med"].notna().sum()
    has_flood = (oaza["flood_rank"] > 0).sum()
    has_price = oaza["price_med"].notna().sum()
    has_crime = oaza["crime_total"].notna().sum()
    has_liq = oaza["liq_max"].notna().sum()
    has_access = oaza["access_index"].notna().sum()
    has_mansion = oaza["mansion_price_tsubo"].notna().sum()
    has_shops = oaza["shop_total"].notna().sum()
    has_medical = oaza["medical_total"].notna().sum()
    print(f"  Matched: {has_boring} boring, {has_flood} flood, {has_price} price, {has_crime} crime, {has_liq} liq, {has_access} access, {has_mansion} mansion, {has_shops} shops, {has_medical} medical")

    # Compute 偏差値
    # Ground score: lower n50_med = shallower bedrock = better → invert
    oaza["ground_score"] = compute_deviation_score(
        oaza["n50_med"].fillna(oaza["n50_med"].median()).values,
        invert=True,
    )

    # Flood score: lower flood_rank = less risk = better → invert
    oaza["flood_score"] = compute_deviation_score(
        oaza["flood_rank"].values,
        invert=True,
    )

    # Price score: only for oaza with actual price data
    has_price_mask = oaza["price_med"].notna()
    price_scores = np.full(len(oaza), np.nan)
    if has_price_mask.sum() > 1:
        price_scores[has_price_mask] = compute_deviation_score(
            oaza.loc[has_price_mask, "price_med"].values,
            invert=True,
        )
    oaza["price_score"] = price_scores

    # Crime score: lower crime = safer = better → invert
    has_crime_mask = oaza["crime_total"].notna()
    crime_scores = np.full(len(oaza), np.nan)
    if has_crime_mask.sum() > 1:
        crime_scores[has_crime_mask] = compute_deviation_score(
            oaza.loc[has_crime_mask, "crime_total"].values,
            invert=True,
        )
    oaza["crime_score"] = crime_scores

    # Liquefaction score: lower liq_max = less risk = better → invert
    has_liq_mask = oaza["liq_max"].notna()
    liq_scores = np.full(len(oaza), np.nan)
    if has_liq_mask.sum() > 1:
        liq_scores[has_liq_mask] = compute_deviation_score(
            oaza.loc[has_liq_mask, "liq_max"].values,
            invert=True,
        )
    oaza["liq_score"] = liq_scores

    # Access score: lower access_index = closer to downtown = better → invert
    has_access_mask = oaza["access_index"].notna()
    access_scores = np.full(len(oaza), np.nan)
    if has_access_mask.sum() > 1:
        access_scores[has_access_mask] = compute_deviation_score(
            oaza.loc[has_access_mask, "access_index"].values,
            invert=True,
        )
    oaza["access_score"] = access_scores

    # Mansion score: lower price = more affordable = better → invert
    has_mansion_mask = oaza["mansion_price_tsubo"].notna()
    mansion_scores = np.full(len(oaza), np.nan)
    if has_mansion_mask.sum() > 1:
        mansion_scores[has_mansion_mask] = compute_deviation_score(
            oaza.loc[has_mansion_mask, "mansion_price_tsubo"].values,
            invert=True,
        )
    oaza["mansion_score"] = mansion_scores

    # Shops score: more shops = better → NOT inverted
    has_shops_mask = oaza["shop_total"].notna()
    shops_scores = np.full(len(oaza), np.nan)
    if has_shops_mask.sum() > 1:
        shops_scores[has_shops_mask] = compute_deviation_score(
            oaza.loc[has_shops_mask, "shop_total"].values,
            invert=False,
        )
    oaza["shops_score"] = shops_scores

    # Medical score: more facilities = better → NOT inverted
    has_medical_mask = oaza["medical_total"].notna()
    medical_scores = np.full(len(oaza), np.nan)
    if has_medical_mask.sum() > 1:
        medical_scores[has_medical_mask] = compute_deviation_score(
            oaza.loc[has_medical_mask, "medical_total"].values,
            invert=False,
        )
    oaza["medical_score"] = medical_scores

    # Composite: average of available scores
    scores = oaza[["ground_score", "flood_score", "price_score", "crime_score", "liq_score", "access_score", "mansion_score", "shops_score", "medical_score"]]
    oaza["composite"] = scores.mean(axis=1, skipna=True).round(1)

    # Add labels
    oaza["n50_med"] = oaza["n50_med"].round(1)
    oaza["price_med"] = oaza["price_med"].round(0)

    # Replace NaN with 0 for PMTiles output (0 = no data)
    oaza["price_score"] = oaza["price_score"].fillna(0).round(1)
    oaza["crime_score"] = oaza["crime_score"].fillna(0).round(1)
    oaza["liq_score"] = oaza["liq_score"].fillna(0).round(1)
    oaza["access_score"] = oaza["access_score"].fillna(0).round(1)
    oaza["mansion_score"] = oaza["mansion_score"].fillna(0).round(1)
    oaza["shops_score"] = oaza["shops_score"].fillna(0).round(1)
    oaza["medical_score"] = oaza["medical_score"].fillna(0).round(1)

    # Keep only needed columns
    out = oaza[["city", "area", "n50_med", "flood_rank", "price_med", "crime_total", "liq_max", "access_index", "mansion_price_tsubo", "shop_total", "medical_total",
                "ground_score", "flood_score", "price_score", "crime_score", "liq_score", "access_score", "mansion_score", "shops_score", "medical_score",
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
    print(f"  Liq:    mean={out['liq_score'].mean():.1f}, "
          f"min={out['liq_score'].min()}, max={out['liq_score'].max()}")
    print(f"  Access: mean={out['access_score'].mean():.1f}, "
          f"min={out['access_score'].min()}, max={out['access_score'].max()}")
    print(f"  Mansion:mean={out['mansion_score'].mean():.1f}, "
          f"min={out['mansion_score'].min()}, max={out['mansion_score'].max()}")
    print(f"  Shops:  mean={out['shops_score'].mean():.1f}, "
          f"min={out['shops_score'].min()}, max={out['shops_score'].max()}")
    print(f"  Medical:mean={out['medical_score'].mean():.1f}, "
          f"min={out['medical_score'].min()}, max={out['medical_score'].max()}")
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
