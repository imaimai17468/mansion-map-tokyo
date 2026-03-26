"""
Build access.pmtiles: 町丁目ごとの都心アクセス指数

1. 国土数値情報 N02 鉄道データから駅ポイント・路線グラフを構築
2. 各駅から東京・新宿・渋谷・品川への最短乗車時間をBFSで算出
3. 加重アクセス指数 = (東京×6 + 新宿×2 + 渋谷×1 + 品川×1) / 10
4. 町丁目に最寄り駅を割当、徒歩時間を加算
5. tippecanoe で PMTiles に変換
"""

import io
import json
import math
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen

import geopandas as gpd
import numpy as np

from shared import download_oaza

ROOT = Path(__file__).resolve().parent.parent
STATION_GEOJSON = ROOT / "data" / "N02" / "UTF-8" / "N02-24_Station.geojson"
OUTPUT_PATH = ROOT / "public" / "data" / "access.pmtiles"

# Target stations with weights
# 東京:新宿:渋谷:品川 = 6:2:1:1
TARGETS = {
    "東京": 6,
    "新宿": 2,
    "渋谷": 1,
    "品川": 1,
}
TOTAL_WEIGHT = sum(TARGETS.values())

# Approximate time per station (minutes)
TIME_PER_STATION = 2.0
# Transfer penalty (minutes)
TRANSFER_PENALTY = 5.0
# Walking speed (m/min) for cho-chome to nearest station
WALK_SPEED = 80  # ~4.8 km/h


def load_stations():
    """Load station data, group by station group code, compute centroids."""
    print(f"Loading {STATION_GEOJSON}...")
    with open(STATION_GEOJSON) as f:
        data = json.load(f)

    # Group features by group code
    groups = defaultdict(list)
    for feat in data["features"]:
        props = feat["properties"]
        group = props["N02_005g"]
        coords = feat["geometry"]["coordinates"]
        # Get midpoint of LineString
        mid_idx = len(coords) // 2
        lng, lat = coords[mid_idx]
        groups[group].append({
            "name": props["N02_005"],
            "line": props["N02_003"],
            "operator": props["N02_004"],
            "lng": lng,
            "lat": lat,
            "station_code": props["N02_005c"],
        })

    # Build station points (one per group)
    stations = {}
    for group_code, entries in groups.items():
        lngs = [e["lng"] for e in entries]
        lats = [e["lat"] for e in entries]
        name = entries[0]["name"]
        lines = list(set(e["line"] for e in entries))
        station_codes = [e["station_code"] for e in entries]
        stations[group_code] = {
            "name": name,
            "lng": sum(lngs) / len(lngs),
            "lat": sum(lats) / len(lats),
            "lines": lines,
            "station_codes": station_codes,
        }

    print(f"  {len(data['features'])} features → {len(stations)} station groups")

    # Filter to Tokyo metropolitan area (roughly)
    tokyo_stations = {
        k: v for k, v in stations.items()
        if 139.0 < v["lng"] < 140.2 and 35.3 < v["lat"] < 36.0
    }
    print(f"  {len(tokyo_stations)} stations in Tokyo metro area")
    return tokyo_stations, data["features"]


def compute_access_index(stations, _raw_features):
    """Compute weighted access index using distance-based estimation.

    Approximates travel time as: straight-line distance × circuity factor / average speed.
    This is more robust than graph-based routing which suffers from station ordering issues.
    """
    print("Computing access index (distance-based)...")

    # Average train speed (km/h) and circuity factor
    AVG_SPEED_KMH = 35.0
    CIRCUITY = 1.3  # rail paths are ~30% longer than straight line

    # Find target station positions
    target_positions = {}
    for target_name in TARGETS:
        candidates = [v for v in stations.values() if v["name"] == target_name]
        if candidates:
            # Use average position of all entries for this station
            lng = sum(c["lng"] for c in candidates) / len(candidates)
            lat = sum(c["lat"] for c in candidates) / len(candidates)
            target_positions[target_name] = (lat, lng)
            print(f"  {target_name}: ({lat:.4f}, {lng:.4f})")
        else:
            print(f"  WARNING: {target_name} not found!")

    # Compute access index per station
    for group_code, station in stations.items():
        weighted_sum = 0
        total_w = 0
        times_detail = {}

        for target_name, weight in TARGETS.items():
            if target_name not in target_positions:
                continue
            tlat, tlng = target_positions[target_name]
            dist_m = haversine(station["lat"], station["lng"], tlat, tlng)
            # Estimated travel time (minutes)
            travel_min = (dist_m / 1000 * CIRCUITY) / AVG_SPEED_KMH * 60
            travel_min = round(travel_min, 1)
            times_detail[target_name] = travel_min
            weighted_sum += travel_min * weight
            total_w += weight

        if total_w > 0:
            station["access_index"] = round(weighted_sum / total_w, 1)
        else:
            station["access_index"] = None
        station["access_detail"] = times_detail

    valid = sum(1 for s in stations.values() if s.get("access_index") is not None)
    print(f"  {valid}/{len(stations)} stations have access index")

    sorted_stations = sorted(
        [(s["name"], s["access_index"]) for s in stations.values()
         if s.get("access_index") is not None],
        key=lambda x: x[1],
    )
    print("  Top 10 best access:")
    for name, idx in sorted_stations[:10]:
        print(f"    {name}: {idx} min")

    return stations


def haversine(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lng points."""
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def assign_to_chochome(chochome_gdf, stations):
    """Assign nearest station and access index to each cho-chome."""
    print("Assigning stations to cho-chome...")

    # Build station list with access index
    station_list = [
        (s["lng"], s["lat"], s["name"], s["access_index"], s.get("access_detail", {}))
        for s in stations.values()
        if s.get("access_index") is not None
    ]
    station_lngs = np.array([s[0] for s in station_list])
    station_lats = np.array([s[1] for s in station_list])

    # Get cho-chome centroids
    centroids = chochome_gdf.geometry.centroid
    results = []

    for idx, centroid in enumerate(centroids):
        if centroid is None or centroid.is_empty:
            results.append({
                "nearest_station": "", "walk_min": 0,
                "access_index": None, "to_tokyo": 0, "to_shinjuku": 0,
                "to_shibuya": 0, "to_shinagawa": 0,
            })
            continue

        # Find nearest station (vectorized haversine approximation)
        dlat = station_lats - centroid.y
        dlng = station_lngs - centroid.x
        # Simple Euclidean on degrees (good enough for small area)
        dist_approx = dlat**2 + (dlng * math.cos(math.radians(centroid.y)))**2
        nearest_idx = np.argmin(dist_approx)

        slng, slat, sname, access_idx, detail = station_list[nearest_idx]
        dist_m = haversine(centroid.y, centroid.x, slat, slng)
        walk_min = round(dist_m / WALK_SPEED, 1)

        # Total access = station access + walking time
        total_access = round(access_idx + walk_min, 1) if access_idx is not None else None

        results.append({
            "nearest_station": sname,
            "walk_min": walk_min,
            "access_index": total_access,
            "to_tokyo": detail.get("東京", 0),
            "to_shinjuku": detail.get("新宿", 0),
            "to_shibuya": detail.get("渋谷", 0),
            "to_shinagawa": detail.get("品川", 0),
        })

    for col in ["nearest_station", "walk_min", "access_index",
                "to_tokyo", "to_shinjuku", "to_shibuya", "to_shinagawa"]:
        chochome_gdf[col] = [r[col] for r in results]

    has_data = chochome_gdf["access_index"].notna().sum()
    print(f"  {has_data}/{len(chochome_gdf)} cho-chome have access data")

    valid = chochome_gdf[chochome_gdf["access_index"].notna()]
    print(f"  Access index range: {valid['access_index'].min():.1f} ~ {valid['access_index'].max():.1f} min")

    out = chochome_gdf[["city", "area", "nearest_station", "walk_min",
                         "access_index", "to_tokyo", "to_shinjuku",
                         "to_shibuya", "to_shinagawa", "geometry"]].copy()
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
            "-l", "access",
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
    stations, raw_features = load_stations()
    stations = compute_access_index(stations, raw_features)
    result = assign_to_chochome(oaza, stations)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
