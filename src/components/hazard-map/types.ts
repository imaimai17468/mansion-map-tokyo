export type ActiveLayer =
  | "boring"
  | "flood"
  | "composite"
  | "landprice"
  | "crime"
  | "liquefaction"
  | "access"
  | "mansion";

export type ScoreFactor =
  | "ground_score"
  | "flood_score"
  | "liq_score"
  | "price_score"
  | "crime_score"
  | "access_score"
  | "mansion_score";

export const SCORE_FACTORS: { key: ScoreFactor; label: string }[] = [
  { key: "ground_score", label: "地盤" },
  { key: "flood_score", label: "洪水" },
  { key: "liq_score", label: "液状化" },
  { key: "price_score", label: "地価" },
  { key: "crime_score", label: "治安" },
  { key: "access_score", label: "アクセス" },
  { key: "mansion_score", label: "マンション価格" },
];
