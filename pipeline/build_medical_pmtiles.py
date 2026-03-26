"""
Build medical.pmtiles: 大字ごとの医療施設密度

1. e-Stat 大字境界をダウンロード
2. OSM 医療施設 GeoJSON を読み込み
3. 空間結合で大字ごとの施設数を算出
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
MEDICAL_GEOJSON = ROOT / "data" / "tokyo_medical.geojson"
OUTPUT_PATH = ROOT / "public" / "data" / "medical.pmtiles"


def load_medical():
    """Load OSM medical facility data."""
    print(f"Loading {MEDICAL_GEOJSON}...")
    with open(MEDICAL_GEOJSON) as f:
        data = json.load(f)

    records = []
    for feat in data["features"]:
        props = feat.get("properties", {})
        amenity = props.get("amenity", "")
        if amenity not in ("hospital", "clinic", "doctors", "pharmacy"):
            continue
        try:
            geom = shape(feat["geometry"])
            records.append({"geometry": geom, "amenity": amenity})
        except Exception:
            continue

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    from collections import Counter
    counts = Counter(gdf["amenity"])
    print(f"  {len(gdf)} facilities")
    for k, v in counts.most_common():
        print(f"    {k}: {v}")
    return gdf


def spatial_join(oaza_gdf, medical_gdf):
    """Count medical facilities per oaza."""
    print("Spatial join...")
    oaza_gdf["geometry"] = oaza_gdf["geometry"].buffer(0)

    joined = gpd.sjoin(medical_gdf, oaza_gdf, how="inner", predicate="within")

    counts = (
        joined.groupby([joined["index_right"], "amenity"])
        .size()
        .unstack(fill_value=0)
    )

    out = oaza_gdf[["city", "area", "geometry"]].copy()

    for col in ["hospital", "clinic", "doctors", "pharmacy"]:
        out[col + "_cnt"] = 0
        if col in counts.columns:
            out.loc[counts.index, col + "_cnt"] = counts[col].values

    out["medical_total"] = (
        out["hospital_cnt"] + out["clinic_cnt"] + out["doctors_cnt"] + out["pharmacy_cnt"]
    )

    has_data = (out["medical_total"] > 0).sum()
    print(f"  {has_data}/{len(out)} oaza have medical facilities")
    print(f"  Total: {out['medical_total'].sum()}")
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
            "-l", "medical",
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
    medical = load_medical()
    result = spatial_join(oaza, medical)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
