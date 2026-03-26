"""
Build mansion.pmtiles: 町丁目ごとの中古マンション取引価格

1. e-Stat から町丁目境界をダウンロード
2. 不動産情報ライブラリ API から中古マンション取引データを取得
3. 町丁目名で結合、坪単価・㎡単価の中央値を算出
4. tippecanoe で PMTiles に変換
"""

import io
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
import pandas as pd

from shared import download_oaza, normalize, strip_chome

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "public" / "data" / "mansion.pmtiles"

API_BASE = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"

# Japanese era → western year
ERA_MAP = {"令和": 2018, "平成": 1988, "昭和": 1925}


def parse_building_year(s: str):
    """Convert '平成15年' → 2003."""
    if not s:
        return None
    for era, base in ERA_MAP.items():
        if era in s:
            m = re.search(r"(\d+)", s)
            if m:
                return base + int(m.group(1))
    return None


def load_api_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REINFOLIB_API_KEY="):
                return line.split("=", 1)[1].strip()
    key = os.environ.get("REINFOLIB_API_KEY", "")
    if not key:
        print("ERROR: REINFOLIB_API_KEY not found in .env or environment")
        sys.exit(1)
    return key


def fetch_mansion_data(api_key: str) -> list[dict]:
    """Fetch mansion transaction data from 不動産情報ライブラリ API."""
    print("Fetching mansion data from API...")
    all_records = []

    # Fetch 2023-2025 (4 quarters each)
    for year in [2023, 2024, 2025]:
        for quarter in [1, 2, 3, 4]:
            url = f"{API_BASE}?year={year}&quarter={quarter}&area=13&priceClassification=01"
            req = Request(url, headers={
                "Ocp-Apim-Subscription-Key": api_key,
                "User-Agent": "Mozilla/5.0",
            })
            try:
                import gzip
                import json
                with urlopen(req, timeout=30) as resp:
                    raw = resp.read()
                    if raw[:2] == b"\x1f\x8b":
                        raw = gzip.decompress(raw)
                    data = json.loads(raw)

                records = data.get("data", [])
                # Filter for condominiums only
                mansions = [r for r in records if r.get("Type") == "中古マンション等"]
                all_records.extend(mansions)
                print(f"  {year}Q{quarter}: {len(mansions)} mansions (of {len(records)} total)")
            except Exception as e:
                print(f"  {year}Q{quarter}: ERROR {e}")

            time.sleep(2)  # Rate limit

    print(f"Total mansion records: {len(all_records)}")
    return all_records


def process_mansion_data(records: list[dict]) -> pd.DataFrame:
    """Process raw API records into a clean DataFrame."""
    rows = []
    for r in records:
        price = int(r.get("TradePrice", 0) or 0)
        area = float(r.get("Area", 0) or 0)
        if price <= 0 or area <= 0:
            continue

        city = r.get("Municipality", "")
        district = r.get("DistrictName", "")
        floor_plan = r.get("FloorPlan", "")
        building_year = parse_building_year(r.get("BuildingYear", ""))
        age = 2025 - building_year if building_year else None

        # Price per m2 and per tsubo (1 tsubo = 3.30579 m2)
        price_per_m2 = round(price / area)
        price_per_tsubo = round(price / area * 3.30579)

        rows.append({
            "city": city,
            "district": district,
            "price": price,
            "area_m2": area,
            "price_per_m2": price_per_m2,
            "price_per_tsubo": price_per_tsubo,
            "floor_plan": floor_plan,
            "age": age,
        })

    df = pd.DataFrame(rows)
    print(f"  {len(df)} valid records after filtering")
    if len(df) > 0:
        print(f"  Price/m2 median: {df['price_per_m2'].median():,.0f} 円")
        print(f"  Price/tsubo median: {df['price_per_tsubo'].median():,.0f} 円")
    return df


def join_mansion(oaza_gdf, mansion_df):
    """Join mansion data to oaza by city + district name (strip chome from both sides)."""
    print("Joining by name (oaza level)...")

    # Build lookup: city_norm + strip_chome(district) → list of records
    from collections import defaultdict
    lookup = defaultdict(list)
    for _, row in mansion_df.iterrows():
        key = normalize(row["city"]) + "_" + strip_chome(row["district"])
        lookup[key].append(row)

    results = []
    for _, row in oaza_gdf.iterrows():
        key = normalize(row["city"]) + "_" + strip_chome(row["area"])
        records = lookup.get(key, [])

        if records:
            prices_m2 = [r["price_per_m2"] for r in records]
            prices_tsubo = [r["price_per_tsubo"] for r in records]
            ages = [r["age"] for r in records if r["age"] is not None]
            results.append({
                "mansion_price_m2": int(np.median(prices_m2)),
                "mansion_price_tsubo": int(np.median(prices_tsubo)),
                "mansion_cnt": len(records),
                "mansion_age_med": round(np.median(ages), 0) if ages else None,
            })
        else:
            results.append({
                "mansion_price_m2": 0,
                "mansion_price_tsubo": 0,
                "mansion_cnt": 0,
                "mansion_age_med": None,
            })

    for col in ["mansion_price_m2", "mansion_price_tsubo", "mansion_cnt"]:
        oaza_gdf[col] = [r[col] for r in results]
    oaza_gdf["mansion_age_med"] = [r["mansion_age_med"] for r in results]
    oaza_gdf["mansion_age_med"] = oaza_gdf["mansion_age_med"].fillna(0).astype(int)

    # Price label
    oaza_gdf["mansion_label"] = oaza_gdf["mansion_price_tsubo"].apply(
        lambda x: f"{x // 10000}万円/坪" if x > 0 else "データなし"
    )

    has_data = (oaza_gdf["mansion_cnt"] > 0).sum()
    print(f"  Name matched: {has_data}/{len(oaza_gdf)} oaza have mansion data")

    out = oaza_gdf[["city", "area", "mansion_price_m2", "mansion_price_tsubo",
                     "mansion_cnt", "mansion_age_med", "mansion_label",
                     "geometry"]].copy()
    return out


def to_pmtiles(gdf, output_path):
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
        tmp = f.name
    gdf.to_file(tmp, driver="GeoJSON")
    print(f"Wrote temp GeoJSON ({os.path.getsize(tmp) / 1024 / 1024:.1f} MB)")

    subprocess.run(
        [
            "tippecanoe",
            "-o", str(output_path),
            "-l", "mansion",
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
    api_key = load_api_key()
    oaza = download_oaza()
    records = fetch_mansion_data(api_key)
    if not records:
        print("ERROR: No mansion data fetched")
        sys.exit(1)
    mansion_df = process_mansion_data(records)
    result = join_mansion(oaza, mansion_df)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
