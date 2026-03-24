export function formatPopup(p: Record<string, unknown>): string {
  const name = `${p.city ?? ""}${p.area ?? ""}`;
  if (!p.cnt) return `<strong>${name}</strong><br/>データなし`;
  return `<strong>${name}</strong><br/>
    N&gt;50 中央値: ${p.n50_med}m<br/>
    N&gt;50 平均: ${p.n50_avg}m<br/>
    N&gt;50 範囲: ${p.n50_min}〜${p.n50_max}m<br/>
    ボーリング数: ${p.cnt}件`;
}
