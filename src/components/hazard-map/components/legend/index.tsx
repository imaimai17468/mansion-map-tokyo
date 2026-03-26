import { memo, useState } from "react";
import type { ActiveLayer, ScoreFactor } from "../../types";
import { SCORE_FACTORS } from "../../types";

const DESCRIPTIONS: Record<ActiveLayer, string> = {
  composite:
    "地盤・洪水・液状化・地価・治安・アクセス・マンション価格の7指標を偏差値化（平均50）し、平均したスコア。高いほど総合的に優れた立地。",
  boring:
    "N値50以上に達する深さの中央値。浅いほど硬い地盤（良好）。KuniJibanボーリングデータより。",
  flood: "想定最大規模降雨時の浸水深（国土数値情報A31a）。町丁目内で最も深い浸水ランクを表示。",
  liquefaction: "PL値に基づく液状化危険度（東京都建設局）。低/中/高の3段階。",
  landprice: "国土数値情報L01の公示地価（2025年）。町丁目内の地点中央値（円/m²）。",
  crime: "警視庁発表の町丁別認知件数（2025年）。凶悪犯・粗暴犯・窃盗などの内訳も確認可能。",
  access:
    "主要駅への推定所要時間の加重平均（東京×6 + 新宿×2 + 渋谷×1 + 品川×1）。徒歩時間込み。小さいほど良好。",
  mansion:
    "不動産情報ライブラリAPIによる中古マンション取引価格（2023-2025年）。町丁目の坪単価中央値を表示。",
};

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

function InfoToggle({ activeLayer }: { activeLayer: ActiveLayer }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          border: "1px solid #ccc",
          background: open ? "#eee" : "white",
          cursor: "pointer",
          fontSize: 11,
          fontWeight: 700,
          color: "#888",
          padding: 0,
          lineHeight: "16px",
          marginLeft: 6,
          flexShrink: 0,
        }}
        aria-label="説明を表示"
      >
        ?
      </button>
      {open && (
        <div style={{ marginTop: 6, color: "#666", fontSize: 10, lineHeight: 1.5 }}>
          {DESCRIPTIONS[activeLayer]}
        </div>
      )}
    </>
  );
}

export const Legend = memo(function Legend({
  activeLayer,
  selectedFactors,
  onToggleFactor,
}: {
  activeLayer: ActiveLayer;
  selectedFactors?: Set<ScoreFactor>;
  onToggleFactor?: (factor: ScoreFactor) => void;
}) {
  return (
    <div
      style={{
        position: "absolute",
        bottom: 30,
        left: 10,
        ...PANEL_STYLE,
        maxWidth: 220,
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
              display: "flex",
              alignItems: "center",
            }}
          >
            N&gt;50 深度（中央値）
            <InfoToggle activeLayer={activeLayer} />
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
              display: "flex",
              alignItems: "center",
            }}
          >
            洪水浸水想定（想定最大規模）
            <InfoToggle activeLayer={activeLayer} />
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
      {activeLayer === "composite" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            立地安全偏差値
            <InfoToggle activeLayer={activeLayer} />
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
            {["#e74c3c", "#f39c12", "#f1c40f", "#2ecc71", "#1abc9c"].map((c) => (
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
            <span>30</span>
            <span>40</span>
            <span>50</span>
            <span>55</span>
            <span>65</span>
          </div>
          {selectedFactors && onToggleFactor && (
            <div style={{ marginTop: 8, borderTop: "1px solid #eee", paddingTop: 6 }}>
              <div style={{ fontSize: 10, color: "#666", marginBottom: 4 }}>算出項目:</div>
              {SCORE_FACTORS.map(({ key, label }) => (
                <label
                  key={key}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                    cursor: "pointer",
                    fontSize: 10,
                    marginTop: 2,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={selectedFactors.has(key)}
                    onChange={() => onToggleFactor(key)}
                    style={{ width: 12, height: 12 }}
                  />
                  {label}
                </label>
              ))}
            </div>
          )}
        </div>
      )}
      {activeLayer === "landprice" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            公示地価（2025年・中央値）
            <InfoToggle activeLayer={activeLayer} />
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
            <span>10万</span>
            <span>30万</span>
            <span>60万</span>
            <span>100万</span>
            <span>500万~</span>
          </div>
          <div style={{ marginTop: 3, color: "#666" }}>円/m²</div>
        </div>
      )}
      {activeLayer === "crime" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            犯罪認知件数（2025年）
            <InfoToggle activeLayer={activeLayer} />
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
            <span>0</span>
            <span>10</span>
            <span>30</span>
            <span>80</span>
            <span>200~</span>
          </div>
          <div style={{ marginTop: 3, color: "#666" }}>件/年</div>
        </div>
      )}
      {activeLayer === "liquefaction" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            液状化リスク（PL値）
            <InfoToggle activeLayer={activeLayer} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            {[
              { color: "#2ecc71", label: "低（PL≦5）" },
              { color: "#f39c12", label: "中（5<PL≦15）" },
              { color: "#e74c3c", label: "高（PL>15）" },
            ].map(({ color, label }) => (
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
      {activeLayer === "access" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            都心アクセス指数
            <InfoToggle activeLayer={activeLayer} />
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
            {["#1abc9c", "#2ecc71", "#f1c40f", "#e67e22", "#e74c3c"].map((c) => (
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
            <span>5</span>
            <span>15</span>
            <span>30</span>
            <span>45</span>
            <span>60分~</span>
          </div>
          <div style={{ marginTop: 3, color: "#666", fontSize: 10 }}>
            東京×6 + 新宿×2 + 渋谷×1 + 品川×1
          </div>
        </div>
      )}
      {activeLayer === "mansion" && (
        <div>
          <div
            style={{
              fontWeight: 600,
              marginBottom: 6,
              fontSize: 12,
              letterSpacing: "0.02em",
              display: "flex",
              alignItems: "center",
            }}
          >
            中古マンション坪単価
            <InfoToggle activeLayer={activeLayer} />
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
            <span>150万</span>
            <span>250万</span>
            <span>400万</span>
            <span>600万</span>
            <span>1000万~</span>
          </div>
          <div style={{ marginTop: 3, color: "#666" }}>円/坪（2023-2025年）</div>
        </div>
      )}
    </div>
  );
});
