// 8-color palette tuned for the MUI light theme. Matches the dashboard's
// sector / vintage / category breakdowns; pick by index, wrap with modulo.
export const CHART_PALETTE = [
  "#1976d2", // primary blue
  "#9c27b0", // purple
  "#2e7d32", // green
  "#ed6c02", // orange
  "#0288d1", // light blue
  "#d32f2f", // red
  "#5d4037", // brown
  "#7b1fa2", // deep purple
];

export function colorFor(index: number): string {
  return CHART_PALETTE[index % CHART_PALETTE.length];
}

// Channel-specific labels surface as legend entries on the channel-mix chart.
export const CHANNEL_LABELS: Record<string, string> = {
  channel_dine_in_lacs: "Dine-in",
  channel_aggregator_a_lacs: "Aggregator A",
  channel_aggregator_b_lacs: "Aggregator B",
  channel_aggregator_d_lacs: "Aggregator D",
  channel_catering_lacs: "Catering / Events",
  channel_franchise_lacs: "Franchise",
};

export const METRIC_LABELS: Record<string, string> = {
  revenue_lacs: "Revenue (L)",
  cogs_lacs: "COGS (L)",
  gross_margin_lacs: "Gross Margin (L)",
  ebitda_lacs: "EBITDA (L)",
  gross_margin_pct: "Gross Margin %",
};
