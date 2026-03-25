import { memo } from "react";
import type { ActiveLayer } from "../../types";

const PANEL_STYLE = {
  background: "white",
  borderRadius: 8,
  padding: "10px 14px",
  boxShadow: "0 2px 8px rgba(0,0,0,0.15)",
  zIndex: 1,
  fontSize: 11,
  color: "#333",
} as const;

export const LayerControl = memo(function LayerControl({
  activeLayer,
  onChange,
}: {
  activeLayer: ActiveLayer;
  onChange: (layer: ActiveLayer) => void;
}) {
  return (
    <div
      style={{
        position: "absolute",
        top: 10,
        left: 10,
        ...PANEL_STYLE,
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 6 }}>レイヤー</div>
      <label style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer" }}>
        <input
          type="radio"
          name="layer"
          checked={activeLayer === "composite"}
          onChange={() => onChange("composite")}
        />
        総合（立地安全偏差値）
      </label>
      <label
        style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", marginTop: 4 }}
      >
        <input
          type="radio"
          name="layer"
          checked={activeLayer === "boring"}
          onChange={() => onChange("boring")}
        />
        地盤（N&gt;50 深度）
      </label>
      <label
        style={{ display: "flex", alignItems: "center", gap: 6, cursor: "pointer", marginTop: 4 }}
      >
        <input
          type="radio"
          name="layer"
          checked={activeLayer === "flood"}
          onChange={() => onChange("flood")}
        />
        洪水浸水想定区域
      </label>
    </div>
  );
});
