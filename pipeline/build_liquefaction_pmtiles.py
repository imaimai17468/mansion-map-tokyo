"""
Build liquefaction.pmtiles: 町丁目ごとの液状化リスク

1. e-Stat から町丁目境界をダウンロード
2. 東京都建設局 PL分布図 GeoJSON を読み込み
3. 空間結合で町丁目ごとの液状化リスクを算出
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

ROOT = Path(__file__).resolve().parent.parent
LIQUEFACTION_GEOJSON = ROOT / "data" / "liquefaction" / "liquefaction_pl.geojson"
OUTPUT_PATH = ROOT / "public" / "data" / "liquefaction.pmtiles"

ESTAT_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search/data"
    "?dlserveyId=A002005212020&code=13&coordSys=1&format=shape"
    "&downloadType=5&datum=2011"
)

# PL区分 → numeric risk (higher = worse)
PL_RANK = {
    "小（0≦PL≦5）": 1,
    "中（5<PL≦15）": 2,
    "大（PL>15）": 3,
}

PL_LABEL = {
    0: "データなし",
    1: "低（PL≦5）",
    2: "中（5<PL≦15）",
    3: "高（PL>15）",
}


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
    print(f"  {len(gdf)} cho-chome")
    return gdf


def load_liquefaction():
    """Load liquefaction point data."""
    print(f"Loading {LIQUEFACTION_GEOJSON}...")
    with open(LIQUEFACTION_GEOJSON) as f:
        data = json.load(f)

    from shapely.geometry import shape

    records = []
    for feat in data["features"]:
        pl_class = feat["properties"].get("PL区分", "")
        rank = PL_RANK.get(pl_class, 0)
        if rank == 0:
            continue
        try:
            geom = shape(feat["geometry"])
            records.append({"geometry": geom, "pl_rank": rank})
        except Exception:
            continue

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    print(f"  {len(gdf)} liquefaction points")

    from collections import Counter
    counts = Counter(gdf["pl_rank"])
    for rank, count in sorted(counts.items()):
        print(f"    Rank {rank} ({PL_LABEL[rank]}): {count}")
    return gdf


def spatial_join(chochome_gdf, liq_gdf):
    """Assign liquefaction risk to each cho-chome."""
    print("Spatial join...")
    chochome_gdf["geometry"] = chochome_gdf["geometry"].buffer(0)

    joined = gpd.sjoin(liq_gdf, chochome_gdf, how="inner", predicate="within")

    # Aggregate: max risk, count of points per risk level
    agg = joined.groupby(joined["index_right"]).agg(
        liq_max=("pl_rank", "max"),
        liq_cnt=("pl_rank", "count"),
        liq_high_cnt=("pl_rank", lambda x: (x == 3).sum()),
        liq_med_cnt=("pl_rank", lambda x: (x == 2).sum()),
        liq_low_cnt=("pl_rank", lambda x: (x == 1).sum()),
    )

    out = chochome_gdf[["city", "area", "geometry"]].copy()
    out = out.join(agg)
    out["liq_max"] = out["liq_max"].fillna(0).astype(int)
    out["liq_cnt"] = out["liq_cnt"].fillna(0).astype(int)
    out["liq_high_cnt"] = out["liq_high_cnt"].fillna(0).astype(int)
    out["liq_med_cnt"] = out["liq_med_cnt"].fillna(0).astype(int)
    out["liq_low_cnt"] = out["liq_low_cnt"].fillna(0).astype(int)
    out["liq_label"] = out["liq_max"].map(PL_LABEL).fillna("データなし")

    # High risk ratio (proportion of high-risk points)
    ratio = np.where(out["liq_cnt"] > 0, out["liq_high_cnt"] / out["liq_cnt"] * 100, 0.0)
    out["liq_high_ratio"] = np.round(ratio, 0).astype(int)

    has_data = (out["liq_cnt"] > 0).sum()
    has_high = (out["liq_max"] == 3).sum()
    print(f"  Result: {has_data}/{len(out)} cho-chome have liquefaction data")
    print(f"  High risk (max): {has_high} cho-chome")
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
            "-l", "liquefaction",
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
    liq = load_liquefaction()
    result = spatial_join(chochome, liq)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
