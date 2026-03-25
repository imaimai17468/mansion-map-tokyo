export function formatPopup(p: Record<string, unknown>): string {
  const name = `${p.city ?? ""}${p.area ?? ""}`;

  // Composite layer
  if ("composite" in p) {
    return `<strong>${name}</strong><br/>
      総合偏差値: <strong>${p.composite}</strong><br/>
      地盤スコア: ${p.ground_score}<br/>
      洪水スコア: ${p.flood_score}`;
  }

  // Flood layer
  if ("flood_rank" in p) {
    if (!p.flood_rank || p.flood_rank === 0) return `<strong>${name}</strong><br/>浸水想定なし`;
    return `<strong>${name}</strong><br/>
      浸水深: ${p.flood_label}<br/>
      最大浸水深: ${p.flood_max}m`;
  }

  // Boring layer
  if (!p.cnt) return `<strong>${name}</strong><br/>データなし`;
  return `<strong>${name}</strong><br/>
    N&gt;50 中央値: ${p.n50_med}m<br/>
    N&gt;50 平均: ${p.n50_avg}m<br/>
    N&gt;50 範囲: ${p.n50_min}〜${p.n50_max}m<br/>
    ボーリング数: ${p.cnt}件`;
}
