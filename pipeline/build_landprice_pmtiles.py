"""
Build landprice.pmtiles: 町丁目ごとの公示地価

1. e-Stat から町丁目境界をダウンロード
2. 国土数値情報 L01 地価公示データをダウンロード
3. 空間結合で町丁目ごとの地価中央値を算出
4. tippecanoe で PMTiles に変換
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np
from shapely.geometry import shape

from shared import download_oaza

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "public" / "data" / "landprice.pmtiles"

# 国土数値情報 L01 地価公示 2025年 東京都
LANDPRICE_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-25/L01-25_13_GML.zip"

USE_LABELS = {
    "000": "住宅地",
    "003": "宅地見込地",
    "005": "商業地",
    "007": "準工業地",
    "009": "工業地",
    "010": "市街化調整区域内宅地",
    "013": "林地",
}


def download_landprice():
    """Download land price GeoJSON from 国土数値情報."""
    print(f"Downloading {LANDPRICE_URL}...")
    with urlopen(LANDPRICE_URL, timeout=120) as resp:
        zip_data = resp.read()
    print(f"  Downloaded {len(zip_data) / 1024 / 1024:.1f} MB")

    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        geojson_files = [n for n in zf.namelist() if n.endswith(".geojson")]
        print(f"  GeoJSON files: {geojson_files}")

        all_points = []
        for gf in geojson_files:
            with zf.open(gf) as f:
                data = json.load(f)
            feats = data.get("features", [])
            for feat in feats:
                props = feat.get("properties", {})
                price = props.get("L01_008")
                use_code = props.get("L01_002", "")
                if price is None or int(price) <= 0:
                    continue
                try:
                    geom = shape(feat["geometry"])
                    all_points.append({
                        "geometry": geom,
                        "price": int(price),
                        "use_code": str(use_code),
                        "use_label": USE_LABELS.get(str(use_code), "その他"),
                        "address": props.get("L01_025", ""),
                        "yoy_change": float(props.get("L01_009", 0) or 0),
                    })
                except Exception:
                    continue

    points_gdf = gpd.GeoDataFrame(all_points, crs="EPSG:4326")
    print(f"  {len(points_gdf)} land price points")

    # Stats
    residential = points_gdf[points_gdf["use_code"] == "000"]
    print(f"    Residential: {len(residential)} points, "
          f"median={residential['price'].median():,.0f} 円/m2")
    return points_gdf


def spatial_join(chochome_gdf, price_gdf):
    """Assign land price stats to each cho-chome."""
    print("Spatial join...")
    chochome_gdf["geometry"] = chochome_gdf["geometry"].buffer(0)

    joined = gpd.sjoin(price_gdf, chochome_gdf, how="inner", predicate="within")

    # Aggregate per cho-chome
    agg = (
        joined.groupby(joined["index_right"])
        .agg(
            price_med=("price", "median"),
            price_min=("price", "min"),
            price_max=("price", "max"),
            price_cnt=("price", "count"),
            yoy_med=("yoy_change", "median"),
        )
    )

    out = chochome_gdf[["city", "area", "geometry"]].copy()
    out = out.join(agg)
    out["price_med"] = out["price_med"].round(0)
    out["price_min"] = out["price_min"].fillna(0).astype(int)
    out["price_max"] = out["price_max"].fillna(0).astype(int)
    out["price_cnt"] = out["price_cnt"].fillna(0).astype(int)
    out["yoy_med"] = out["yoy_med"].fillna(0).round(1)

    # Price label (万円/m2)
    out["price_label"] = out["price_med"].apply(
        lambda x: f"{x / 10000:.0f}万円/m²" if x > 0 else "データなし"
    )

    has_price = (out["price_cnt"] > 0).sum()
    print(f"  Result: {has_price}/{len(out)} cho-chome have price data")

    # Stats
    valid = out[out["price_cnt"] > 0]
    print(f"  Price median range: {valid['price_med'].min():,.0f} ~ "
          f"{valid['price_med'].max():,.0f} 円/m2")
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
            "-l", "landprice",
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
    oaza = download_oaza()
    prices = download_landprice()
    result = spatial_join(oaza, prices)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
