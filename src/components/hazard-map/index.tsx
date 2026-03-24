import { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { formatPopup } from "./formatPopup";
import { LayerControl } from "./components/layer-control";
import { Legend } from "./components/legend";
import type { LayerVisibility } from "./types";

const CHOROPLETH_URL = "/data/choropleth.pmtiles";

const DEPTH_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"];
const DEPTH_STEPS = [5, 15, 30, 50];

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
      type: "raster",
      tiles: [
        "https://disaportaldata.gsi.go.jp/raster/01_flood_l2_shinsuishin_data/{z}/{x}/{y}.png",
      ],
      tileSize: 256,
      minzoom: 2,
      maxzoom: 17,
      attribution:
        "出典: <a href='https://disaportal.gsi.go.jp/hazardmapportal/hazardmap/copyright/opendata.html' target='_blank'>ハザードマップポータルサイト</a>",
    },
  },
  layers: [{ id: "carto", type: "raster", source: "carto" }],
};

const BORING_LAYER_IDS = ["choropleth-fill", "choropleth-line"];
const FLOOD_LAYER_ID = "flood-overlay";

export default function HazardMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [layers, setLayers] = useState<LayerVisibility>({ boring: true, flood: false });

  const handleToggle = (layer: keyof LayerVisibility) => {
    setLayers((prev) => ({ ...prev, [layer]: !prev[layer] }));
  };

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
      });

      // Flood raster layer (above choropleth-fill, below boundary lines)
      map.addLayer({
        id: FLOOD_LAYER_ID,
        type: "raster",
        source: "flood",
        paint: { "raster-opacity": 0.7 },
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
      });

      map.on("click", "choropleth-fill", handleClick);
      map.on("mouseenter", "choropleth-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "choropleth-fill", () => {
        map.getCanvas().style.cursor = "";
      });

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
    if (!map || !map.getLayer(FLOOD_LAYER_ID)) return;

    map.setLayoutProperty(FLOOD_LAYER_ID, "visibility", layers.flood ? "visible" : "none");
    for (const id of BORING_LAYER_IDS) {
      map.setLayoutProperty(id, "visibility", layers.boring ? "visible" : "none");
    }
  }, [layers]);

  return (
    <div style={{ position: "relative", width: "100%", height: "100vh" }}>
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />
      <LayerControl layers={layers} onToggle={handleToggle} />
      <Legend layers={layers} />
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
