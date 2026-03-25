"""
Build flood.pmtiles: 町丁目ごとの洪水浸水想定データ

1. e-Stat から町丁目境界 Shapefile をダウンロード
2. 国土数値情報 A31a 洪水浸水想定区域データをダウンロード
3. 空間結合で町丁目ごとの最大浸水深ランクを算出
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
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "public" / "data" / "flood.pmtiles"

# e-Stat 2020 国勢調査 小地域 境界データ (東京都)
ESTAT_URL = (
    "https://www.e-stat.go.jp/gis/statmap-search/data"
    "?dlserveyId=A002005212020&code=13&coordSys=1&format=shape"
    "&downloadType=5&datum=2011"
)

# 国土数値情報 A31a 洪水浸水想定区域 東京都
FLOOD_URLS = [
    "https://nlftp.mlit.go.jp/ksj/gml/data/A31a/A31a-23/A31a-23_13_10_GEOJSON.zip",
    "https://nlftp.mlit.go.jp/ksj/gml/data/A31a/A31a-23/A31a-23_13_20_GEOJSON.zip",
]

# 浸水深ランクコード → 代表値 (m)
DEPTH_RANK = {
    "1": 0.25, "2": 1.75, "3": 4.0, "4": 7.5, "5": 15.0, "6": 25.0,
}
DEPTH_LABEL = {
    0: "浸水想定なし",
    1: "~0.5m", 2: "0.5~3m", 3: "3~5m", 4: "5~10m", 5: "10~20m", 6: "20m~",
}


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

    # Find .shp file
    shp_files = list(Path(tmpdir).rglob("*.shp"))
    if not shp_files:
        print("ERROR: No .shp file found in download")
        sys.exit(1)

    gdf = gpd.read_file(shp_files[0])
    print(f"  {len(gdf)} polygons, columns: {list(gdf.columns)}")

    # Rename to match existing choropleth naming
    gdf = gdf.rename(columns={"CITY_NAME": "city", "S_NAME": "area"})
    # Filter out records without cho-chome name
    gdf = gdf[gdf["area"].notna() & (gdf["area"] != "")].copy()
    # Ensure WGS84
    gdf = gdf.to_crs("EPSG:4326")
    print(f"  {len(gdf)} cho-chome with names")
    return gdf


def download_flood_data():
    """Download flood GeoJSON from 国土数値情報."""
    all_features = []
    for url in FLOOD_URLS:
        print(f"Downloading {url}...")
        with urlopen(url, timeout=120) as resp:
            zip_data = resp.read()
        print(f"  Downloaded {len(zip_data) / 1024 / 1024:.1f} MB")

        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
            geojson_files = [n for n in zf.namelist() if n.endswith(".geojson")]
            for gf in geojson_files:
                with zf.open(gf) as f:
                    data = json.load(f)
                feats = data.get("features", [])
                if not feats:
                    continue
                props = feats[0].get("properties", {})
                depth_field = None
                for candidate in ["A31a_205", "A31a_105"]:
                    if candidate in props:
                        depth_field = candidate
                        break
                if depth_field:
                    print(f"    {Path(gf).name}: {len(feats)} features (depth={depth_field})")
                    for feat in feats:
                        feat["_depth_field"] = depth_field
                    all_features.extend(feats)

    print(f"Total flood features with depth: {len(all_features)}")
    return all_features


def spatial_join(chochome_gdf, flood_features):
    """Assign max flood depth to each cho-chome."""
    print("Building flood GeoDataFrame...")
    flood_records = []
    for feat in flood_features:
        props = feat.get("properties", {})
        depth_field = feat.get("_depth_field", "A31a_205")
        rank = str(props.get(depth_field, "0"))
        depth = DEPTH_RANK.get(rank, 0)
        if depth == 0:
            continue
        try:
            geom = shape(feat["geometry"])
            if not geom.is_valid:
                geom = geom.buffer(0)
            flood_records.append({"geometry": geom, "depth": depth, "rank": int(rank)})
        except Exception:
            continue

    flood_gdf = gpd.GeoDataFrame(flood_records, crs="EPSG:4326")
    print(f"  {len(flood_gdf)} flood polygons")

    # Fix any invalid geometries in cho-chome
    chochome_gdf["geometry"] = chochome_gdf["geometry"].buffer(0)

    print("Spatial join (this may take a minute)...")
    joined = gpd.sjoin(chochome_gdf, flood_gdf, how="left", predicate="intersects")

    result = (
        joined.groupby(joined.index)
        .agg(
            flood_max=("depth", "max"),
            flood_rank=("rank", "max"),
        )
    )

    out = chochome_gdf[["city", "area", "geometry"]].copy()
    out = out.join(result)
    out["flood_max"] = out["flood_max"].fillna(0).round(2)
    out["flood_rank"] = out["flood_rank"].fillna(0).astype(int)
    out["flood_label"] = out["flood_rank"].map(DEPTH_LABEL).fillna("浸水想定なし")

    has_flood = (out["flood_rank"] > 0).sum()
    print(f"  Result: {has_flood}/{len(out)} cho-chome have flood risk")
    return out


def to_pmtiles(gdf, output_path):
    """Export GeoDataFrame to PMTiles via tippecanoe."""
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
        tmp = f.name
    gdf.to_file(tmp, driver="GeoJSON")
    size_mb = os.path.getsize(tmp) / 1024 / 1024
    print(f"Wrote temp GeoJSON: {tmp} ({size_mb:.1f} MB)")

    print(f"Running tippecanoe -> {output_path}...")
    subprocess.run(
        [
            "tippecanoe",
            "-o", str(output_path),
            "-l", "flood",
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
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Done! {output_path} ({size_mb:.1f} MB)")


def main():
    chochome = download_chochome()
    flood = download_flood_data()
    if not flood:
        print("ERROR: No flood data")
        sys.exit(1)
    result = spatial_join(chochome, flood)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
