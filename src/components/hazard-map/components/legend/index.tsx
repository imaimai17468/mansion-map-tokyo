import { memo } from "react";
import type { ActiveLayer } from "../../types";

const DEPTH_COLORS = ["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad"];

const FLOOD_LEGEND = [
  { color: "#F7F1A0", label: "~0.5m" },
  { color: "#F6E26B", label: "0.5~3m" },
  { color: "#F2A85B", label: "3~5m" },
  { color: "#E87B5A", label: "5~10m" },
  { color: "#D44D6E", label: "10~20m" },
  { color: "#9B3FA3", label: "20m~" },
];

const PANEL_STYLE = {
  background: "white",
  borderRadius: 8,
  padding: "10px 14px",
  boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
  zIndex: 1,
  fontSize: 11,
  color: "#333",
} as const;

export const Legend = memo(function Legend({ activeLayer }: { activeLayer: ActiveLayer }) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 30,
        left: 10,
        ...PANEL_STYLE,
      }}
    >
      {activeLayer === "boring" && (
        <div>
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
            {DEPTH_COLORS.map((c) => (
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
              color: "#767676",
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
      )}
      {activeLayer === "flood" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
            }}
          >
            洪水浸水想定（想定最大規模）
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {FLOOD_LEGEND.map(({ color, label }) => (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span
                  style={{
                    width: 14,
                    height: 10,
                    borderRadius: 2,
                    background: color,
                    display: "inline-block",
                  }}
                />
                {label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
});
