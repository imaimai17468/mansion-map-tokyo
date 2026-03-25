import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { formatPopup } from "./formatPopup";
import { LayerControl } from "./components/layer-control";
import { Legend } from "./components/legend";
import type { ActiveLayer } from "./types";

const CHOROPLETH_URL = "/data/choropleth.pmtiles";
const FLOOD_URL = "/data/flood.pmtiles";
const COMPOSITE_URL = "/data/composite.pmtiles";
const LANDPRICE_URL = "/data/landprice.pmtiles";
const CRIME_URL_TILE = "/data/crime.pmtiles";

const DEPTH_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"];
const DEPTH_STEPS = [5, 15, 30, 50];

const FLOOD_COLORS = ["#F7F1A0", "#F6E26B", "#F2A85B", "#E87B5A", "#D44D6E", "#9B3FA3"];
const FLOOD_STEPS = [1, 2, 3, 4, 5, 6];

// Register PMTiles protocol once at module level
const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const MAP_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    carto: {
      type: "raster",
      tiles: ["https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}@2x.png"],
      tileSize: 256,
      attribution:
        "&copy; <a href='https://carto.com/'>CARTO</a>, &copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors",
    },
    choropleth: {
      type: "vector",
      url: `pmtiles://${CHOROPLETH_URL}`,
    },
    flood: {
      type: "vector",
      url: `pmtiles://${FLOOD_URL}`,
      attribution:
        "出典: <a href='https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/opendata.html' target='_blank'>ハザードマップポータルサイト</a>",
    },
    composite: {
      type: "vector",
      url: `pmtiles://${COMPOSITE_URL}`,
    },
    landprice: {
      type: "vector",
      url: `pmtiles://${LANDPRICE_URL}`,
    },
    crime: {
      type: "vector",
      url: `pmtiles://${CRIME_URL_TILE}`,
    },
  },
  layers: [{ id: "carto", type: "raster", source: "carto" }],
};

const BORING_LAYER_IDS = ["choropleth-fill", "choropleth-line"];
const FLOOD_LAYER_IDS = ["flood-fill", "flood-line"];
const COMPOSITE_LAYER_IDS = ["composite-fill", "composite-line"];
const LANDPRICE_LAYER_IDS = ["landprice-fill", "landprice-line"];
const CRIME_LAYER_IDS = ["crime-fill", "crime-line"];

export default function HazardMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeLayer, setActiveLayer] = useState<ActiveLayer>("composite");

  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: [139.7671, 35.6812],
      zoom: 12,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl());

    const handleClick = (
      e: maplibregl.MapMouseEvent & { features?: maplibregl.GeoJSONFeature[] },
    ) => {
      const feature = e.features?.[0];
      if (!feature) return;

      if (!popupRef.current) {
        popupRef.current = new maplibregl.Popup({ offset: 10 });
      }
      popupRef.current
        .setLngLat(e.lngLat)
        .setHTML(
          `<div style="font-size:13px;line-height:1.6">${formatPopup(feature.properties)}</div>`,
        )
        .addTo(map);
    };

    const onLoad = () => {
      map.addLayer({
        id: "choropleth-fill",
        type: "fill",
        source: "choropleth",
        "source-layer": "choropleth",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "cnt"], 0],
            "rgba(200,200,200,0.3)",
            [
              "step",
              ["get", "n50_med"],
              DEPTH_COLORS[0],
              ...DEPTH_STEPS.flatMap((s, i) => [s, DEPTH_COLORS[i + 1]]),
            ],
          ],
          "fill-opacity": 0.6,
        },
        layout: { visibility: "none" },
      });

      map.addLayer({
        id: "choropleth-line",
        type: "line",
        source: "choropleth",
        "source-layer": "choropleth",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 14, 1],
        },
        layout: { visibility: "none" },
      });

      // Flood vector layers (initially hidden)
      map.addLayer({
        id: "flood-fill",
        type: "fill",
        source: "flood",
        "source-layer": "flood",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "flood_rank"], 0],
            "rgba(200,200,200,0.3)",
            [
              "step",
              ["get", "flood_rank"],
              FLOOD_COLORS[0],
              ...FLOOD_STEPS.slice(1).flatMap((s, i) => [s, FLOOD_COLORS[i + 1]]),
            ],
          ],
          "fill-opacity": 0.6,
        },
        layout: { visibility: "none" },
      });

      map.addLayer({
        id: "flood-line",
        type: "line",
        source: "flood",
        "source-layer": "flood",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 14, 1],
        },
        layout: { visibility: "none" },
      });

      // Composite vector layers (default visible)
      map.addLayer({
        id: "composite-fill",
        type: "fill",
        source: "composite",
        "source-layer": "composite",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "composite"],
            30,
            "#e74c3c",
            40,
            "#f39c12",
            50,
            "#f1c40f",
            55,
            "#2ecc71",
            65,
            "#1abc9c",
          ],
          "fill-opacity": 0.6,
        },
      });

      map.addLayer({
        id: "composite-line",
        type: "line",
        source: "composite",
        "source-layer": "composite",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 14, 1],
        },
      });

      // Land price vector layers (initially hidden)
      map.addLayer({
        id: "landprice-fill",
        type: "fill",
        source: "landprice",
        "source-layer": "landprice",
        paint: {
          "fill-color": [
            "case",
            ["==", ["get", "price_cnt"], 0],
            "rgba(200,200,200,0.3)",
            [
              "interpolate",
              ["linear"],
              ["get", "price_med"],
              100000,
              "#2ecc71",
              300000,
              "#f1c40f",
              600000,
              "#e67e22",
              1000000,
              "#e74c3c",
              5000000,
              "#8e44ad",
            ],
          ],
          "fill-opacity": 0.6,
        },
        layout: { visibility: "none" },
      });

      map.addLayer({
        id: "landprice-line",
        type: "line",
        source: "landprice",
        "source-layer": "landprice",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 14, 1],
        },
        layout: { visibility: "none" },
      });

      // Crime vector layers (initially hidden)
      map.addLayer({
        id: "crime-fill",
        type: "fill",
        source: "crime",
        "source-layer": "crime",
        paint: {
          "fill-color": [
            "interpolate",
            ["linear"],
            ["get", "crime_total"],
            0,
            "#2ecc71",
            10,
            "#f1c40f",
            30,
            "#e67e22",
            80,
            "#e74c3c",
            200,
            "#8e44ad",
          ],
          "fill-opacity": 0.6,
        },
        layout: { visibility: "none" },
      });

      map.addLayer({
        id: "crime-line",
        type: "line",
        source: "crime",
        "source-layer": "crime",
        paint: {
          "line-color": "#fff",
          "line-width": ["interpolate", ["linear"], ["zoom"], 8, 0.2, 14, 1],
        },
        layout: { visibility: "none" },
      });

      const clickLayers = [
        "choropleth-fill",
        "flood-fill",
        "composite-fill",
        "landprice-fill",
        "crime-fill",
      ];
      for (const id of clickLayers) {
        map.on("click", id, handleClick);
        map.on("mouseenter", id, () => {
          map.getCanvas().style.cursor = "pointer";
        });
        map.on("mouseleave", id, () => {
          map.getCanvas().style.cursor = "";
        });
      }

      setIsLoading(false);
    };

    if (map.isStyleLoaded()) {
      onLoad();
    } else {
      map.on("load", onLoad);
    }

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Sync layer visibility with map
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer("flood-fill")) return;

    for (const id of BORING_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", activeLayer === "boring" ? "visible" : "none");
    }
    for (const id of FLOOD_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", activeLayer === "flood" ? "visible" : "none");
    }
    for (const id of COMPOSITE_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", activeLayer === "composite" ? "visible" : "none");
    }
    for (const id of LANDPRICE_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", activeLayer === "landprice" ? "visible" : "none");
    }
    for (const id of CRIME_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", activeLayer === "crime" ? "visible" : "none");
    }
  }, [activeLayer]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100vh" }}>
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
      <LayerControl activeLayer={activeLayer} onChange={setActiveLayer} />
      <Legend activeLayer={activeLayer} />
      {isLoading && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(255,255,255,0.7)",
            zIndex: 2,
            fontSize: 14,
            color: "#666",
          }}
        >
          地図データを読み込み中...
        </div>
      )}
    </div>
  );
}
