export function formatPopup(p: Record<string, unknown>): string {
  const name = `${p.city ?? ""}${p.area ?? ""}`;

  // Access layer
  if ("access_index" in p && !("composite" in p)) {
    return `<strong>${name}</strong><br/>
      最寄駅: ${p.nearest_station}（徒歩${p.walk_min}分）<br/>
      アクセス指数: <strong>${p.access_index}分</strong><br/>
      → 東京: ${p.to_tokyo}分<br/>
      → 新宿: ${p.to_shinjuku}分<br/>
      → 渋谷: ${p.to_shibuya}分<br/>
      → 品川: ${p.to_shinagawa}分`;
  }

  // Composite layer (check before price_med since composite also has price_med)
  if ("composite" in p) {
    const priceStr = p.price_score && p.price_score !== 0 ? `${p.price_score}` : "データなし";
    const crimeStr = p.crime_score && p.crime_score !== 0 ? `${p.crime_score}` : "データなし";
    const liqStr = p.liq_score && p.liq_score !== 0 ? `${p.liq_score}` : "データなし";
    const accessStr = p.access_score && p.access_score !== 0 ? `${p.access_score}` : "データなし";
    return `<strong>${name}</strong><br/>
      総合偏差値: <strong>${p.composite}</strong><br/>
      地盤スコア: ${p.ground_score}<br/>
      洪水スコア: ${p.flood_score}<br/>
      液状化スコア: ${liqStr}<br/>
      地価スコア: ${priceStr}<br/>
      治安スコア: ${crimeStr}<br/>
      アクセススコア: ${accessStr}`;
  }

  // Liquefaction layer
  if ("liq_max" in p && !("composite" in p)) {
    if (!p.liq_cnt || p.liq_cnt === 0) return `<strong>${name}</strong><br/>液状化データなし`;
    return `<strong>${name}</strong><br/>
      最大リスク: ${p.liq_label}<br/>
      高リスク率: ${p.liq_high_ratio}%<br/>
      調査地点数: ${p.liq_cnt}`;
  }

  // Crime layer
  if ("crime_total" in p && !("composite" in p) && !("price_med" in p)) {
    return `<strong>${name}</strong><br/>
      犯罪総数: ${p.crime_total}件<br/>
      凶悪犯: ${p.crime_violent}件<br/>
      粗暴犯: ${p.crime_assault}件<br/>
      侵入窃盗: ${p.crime_burglary}件<br/>
      非侵入窃盗: ${p.crime_theft}件`;
  }

  // Land price layer
  if ("price_med" in p) {
    if (!p.price_cnt || p.price_cnt === 0) return `<strong>${name}</strong><br/>地価データなし`;
    const yoy = Number(p.yoy_med);
    const yoyStr = yoy > 0 ? `+${yoy}%` : `${yoy}%`;
    return `<strong>${name}</strong><br/>
      地価中央値: ${p.price_label}<br/>
      前年比: ${yoyStr}<br/>
      地点数: ${p.price_cnt}`;
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
