"""
Rebuild choropleth.pmtiles at oaza (大字・町) level.

1. Extract boring attributes from existing choropleth.pmtiles (chome level)
2. Download oaza boundaries from e-Stat
3. Aggregate boring stats by oaza (weighted by count)
4. Output as PMTiles
"""

import gzip
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import geopandas as gpd
import mapbox_vector_tile
import numpy as np
from pmtiles.reader import MmapSource, Reader

sys.path.insert(0, str(Path(__file__).parent))
from shared import download_oaza, strip_chome

ROOT = Path(__file__).resolve().parent.parent
CHOROPLETH_PATH = ROOT / "public" / "data" / "choropleth.pmtiles"
OUTPUT_PATH = ROOT / "public" / "data" / "choropleth.pmtiles"


def extract_boring_data():
    """Extract all boring attributes from existing PMTiles."""
    print(f"Extracting from {CHOROPLETH_PATH}...")
    records = defaultdict(list)

    with open(CHOROPLETH_PATH, "rb") as f:
        reader = Reader(MmapSource(f))
        header = reader.header()
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
                        oaza_key = f"{city}_{strip_chome(area)}"
                        records[oaza_key].append({
                            "n50_med": props.get("n50_med"),
                            "n50_avg": props.get("n50_avg"),
                            "n50_min": props.get("n50_min"),
                            "n50_max": props.get("n50_max"),
                            "cnt": props.get("cnt", 0),
                            "city": city,
                        })

    print(f"  {sum(len(v) for v in records.values())} chome records → {len(records)} oaza groups")
    return records


def aggregate_boring(oaza_gdf, boring_data):
    """Aggregate boring stats to oaza level."""
    print("Aggregating boring data to oaza...")

    results = []
    for _, row in oaza_gdf.iterrows():
        key = f"{row['city']}_{strip_chome(row['area'])}"
        entries = boring_data.get(key, [])

        if entries:
            # Weight by cnt for proper aggregation
            total_cnt = sum(e.get("cnt", 0) or 0 for e in entries)
            valid_meds = [e["n50_med"] for e in entries if e.get("n50_med") is not None]
            valid_mins = [e["n50_min"] for e in entries if e.get("n50_min") is not None]
            valid_maxs = [e["n50_max"] for e in entries if e.get("n50_max") is not None]

            if valid_meds:
                # Weighted average for median/avg, min of mins, max of maxes
                weights = [e.get("cnt", 1) or 1 for e in entries if e.get("n50_med") is not None]
                n50_med = round(np.average(valid_meds, weights=weights), 1)
                n50_avg = round(np.average(
                    [e["n50_avg"] for e in entries if e.get("n50_avg") is not None],
                    weights=[e.get("cnt", 1) or 1 for e in entries if e.get("n50_avg") is not None],
                ), 1)
                n50_min = round(min(valid_mins), 1) if valid_mins else None
                n50_max = round(max(valid_maxs), 1) if valid_maxs else None
            else:
                n50_med = n50_avg = n50_min = n50_max = None

            results.append({
                "cnt": total_cnt,
                "n50_med": n50_med,
                "n50_avg": n50_avg,
                "n50_min": n50_min,
                "n50_max": n50_max,
            })
        else:
            results.append({"cnt": 0, "n50_med": None, "n50_avg": None, "n50_min": None, "n50_max": None})

    for col in ["cnt", "n50_med", "n50_avg", "n50_min", "n50_max"]:
        oaza_gdf[col] = [r[col] for r in results]

    oaza_gdf["cnt"] = oaza_gdf["cnt"].fillna(0).astype(int)

    has_data = (oaza_gdf["cnt"] > 0).sum()
    print(f"  {has_data}/{len(oaza_gdf)} oaza have boring data")
    return oaza_gdf[["city", "area", "cnt", "n50_med", "n50_avg", "n50_min", "n50_max", "geometry"]].copy()


def to_pmtiles(gdf, output_path):
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False, mode="w") as f:
        tmp = f.name
    gdf.to_file(tmp, driver="GeoJSON")
    print(f"Wrote temp GeoJSON ({os.path.getsize(tmp) / 1024 / 1024:.1f} MB)")

    subprocess.run(
        [
            "tippecanoe",
            "-o", str(output_path),
            "-l", "choropleth",
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
    boring_data = extract_boring_data()
    oaza = download_oaza()
    result = aggregate_boring(oaza, boring_data)
    to_pmtiles(result, OUTPUT_PATH)


if __name__ == "__main__":
    main()
