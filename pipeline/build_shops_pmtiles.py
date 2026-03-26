"""
Build shops.pmtiles: 大字ごとのスーパー・コンビニ密度

1. e-Stat 大字境界をダウンロード
2. OSM スーパー・コンビニ GeoJSON を読み込み
3. 空間結合で大字ごとの店舗数を算出
4. tippecanoe で PMTiles に変換
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).parent))
from shared import download_oaza

ROOT = Path(__file__).resolve().parent.parent
SHOPS_GEOJSON = ROOT / "data" / "tokyo_shops.geojson"
OUTPUT_PATH = ROOT / "public" / "data" / "shops.pmtiles"


def load_shops():
    """Load OSM shop point data."""
    print(f"Loading {SHOPS_GEOJSON}...")
    with open(SHOPS_GEOJSON) as f:
        data = json.load(f)

    records = []
    for feat in data["features"]:
        props = feat.get("properties", {})
        shop_type = props.get("shop", "")
        if shop_type not in ("convenience", "supermarket"):
            continue
        try:
            geom = shape(feat["geometry"])
            records.append({
                "geometry": geom,
                "shop_type": shop_type,
            })
        except Exception:
            continue

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    convenience = (gdf["shop_type"] == "convenience").sum()
    supermarket = (gdf["shop_type"] == "supermarket").sum()
    print(f"  {len(gdf)} shops (convenience: {convenience}, supermarket: {supermarket})")
    return gdf


def spatial_join(oaza_gdf, shops_gdf):
    """Count shops per oaza."""
    print("Spatial join...")
    oaza_gdf["geometry"] = oaza_gdf["geometry"].buffer(0)

    joined = gpd.sjoin(shops_gdf, oaza_gdf, how="inner", predicate="within")

    # Count by type per oaza
    counts = (
        joined.groupby([joined["index_right"], "shop_type"])
        .size()
        .unstack(fill_value=0)
    )

    out = oaza_gdf[["city", "area", "geometry"]].copy()

    if "convenience" in counts.columns:
        out["convenience_cnt"] = 0
        out.loc[counts.index, "convenience_cnt"] = counts["convenience"].values
    else:
        out["convenience_cnt"] = 0

    if "supermarket" in counts.columns:
        out["supermarket_cnt"] = 0
        out.loc[counts.index, "supermarket_cnt"] = counts["supermarket"].values
    else:
        out["supermarket_cnt"] = 0

    out["shop_total"] = out["convenience_cnt"] + out["supermarket_cnt"]

    has_shops = (out["shop_total"] > 0).sum()
    print(f"  {has_shops}/{len(out)} oaza have shops")
    print(f"  Total: convenience={out['convenience_cnt'].sum()}, supermarket={out['supermarket_cnt'].sum()}")
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
            "-l", "shops",
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
    shops = load_shops()
    result = spatial_join(oaza, shops)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
