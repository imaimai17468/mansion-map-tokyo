import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";

const CHOROPLETH_URL = "/data/choropleth.pmtiles";

const DEPTH_COLORS: [number, string][] = [
  [0, "#2ecc71"],
  [5, "#f1c40f"],
  [15, "#e67e22"],
  [30, "#e74c3c"],
  [50, "#8e44ad"],
];

export default function BoringMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
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
        },
        layers: [{ id: "carto", type: "raster", source: "carto" }],
      },
      center: [139.7671, 35.6812],
      zoom: 12,
    });

    map.addControl(new maplibregl.NavigationControl());

    map.on("load", () => {
      // Fill layer
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
              DEPTH_COLORS[0][1],
              DEPTH_COLORS[1][0],
              DEPTH_COLORS[1][1],
              DEPTH_COLORS[2][0],
              DEPTH_COLORS[2][1],
              DEPTH_COLORS[3][0],
              DEPTH_COLORS[3][1],
              DEPTH_COLORS[4][0],
              DEPTH_COLORS[4][1],
            ],
          ],
          "fill-opacity": 0.6,
        },
      });

      // Border layer
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

      // Hover popup
      map.on("click", "choropleth-fill", (e) => {
        const feature = e.features?.[0];
        if (!feature) return;
        const p = feature.properties;

        if (popupRef.current) popupRef.current.remove();

        const hasData = p.cnt > 0;
        popupRef.current = new maplibregl.Popup({ offset: 10 })
          .setLngLat(e.lngLat)
          .setHTML(
            `<div style="font-size:13px;line-height:1.6">
              <strong>${p.city ?? ""}${p.area ?? ""}</strong><br/>
              ${
                hasData
                  ? `N&gt;50 中央値: ${p.n50_med}m<br/>
                     N&gt;50 平均: ${p.n50_avg}m<br/>
                     N&gt;50 範囲: ${p.n50_min}〜${p.n50_max}m<br/>
                     ボーリング数: ${p.cnt}件`
                  : "データなし"
              }
            </div>`,
          )
          .addTo(map);
      });

      map.on("mouseenter", "choropleth-fill", () => {
        map.getCanvas().style.cursor = "pointer";
      });
      map.on("mouseleave", "choropleth-fill", () => {
        map.getCanvas().style.cursor = "";
      });
    });

    mapRef.current = map;

    return () => {
      map.remove();
      maplibregl.removeProtocol("pmtiles");
      mapRef.current = null;
    };
  }, []);

  return (
    <div style={{ position: "relative", width: "100%", height: "100vh" }}>
      <div ref={mapContainer} style={{ width: "100%", height: "100%" }} />

      {/* 凡例 */}
      <div
        style={{
          position: "absolute",
          bottom: 30,
          left: 10,
          background: "white",
          borderRadius: 8,
          padding: "10px 14px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
          zIndex: 1,
          fontSize: 11,
          color: "#333",
        }}
      >
        <div
          style={{
            fontWeight: 600,
            marginBottom: 6,
            fontSize: 12,
            letterSpacing: "0.02em",
          }}
        >
          N&gt;50 深度（中央値）
        </div>
        <div
          style={{
            display: "flex",
            height: 10,
            borderRadius: 5,
            overflow: "hidden",
            width: 180,
          }}
        >
          {["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"].map((c) => (
            <div key={c} style={{ flex: 1, background: c }} />
          ))}
        </div>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            width: 180,
            marginTop: 3,
            color: "#666",
          }}
        >
          <span>0m</span>
          <span>5</span>
          <span>15</span>
          <span>30</span>
          <span>50m+</span>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            marginTop: 6,
            color: "#999",
          }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: 2,
              background: "rgba(200,200,200,0.5)",
              border: "1px solid #ddd",
              display: "inline-block",
              marginRight: 5,
            }}
          />
          データなし
        </div>
      </div>
    </div>
  );
}
