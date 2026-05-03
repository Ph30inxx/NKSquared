import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompanyTimeseries } from "../../../api/timeseries";
import ChartCard from "../../../components/charts/ChartCard";
import {
  CHART_PALETTE,
  METRIC_LABELS,
} from "../../../components/charts/chartPalette";

const METRICS = ["revenue_lacs", "gross_margin_lacs", "ebitda_lacs"] as const;

interface Props {
  companyCode: string;
}

function fmtMonth(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { month: "short", year: "2-digit" });
}

export default function RevenueTimeseriesChart({ companyCode }: Props) {
  const { data, isLoading, error } = useCompanyTimeseries(companyCode, {
    metrics: [...METRICS],
  });

  const rows =
    data?.months.map((m, idx) => {
      const row: Record<string, unknown> = { month: fmtMonth(m) };
      for (const metric of METRICS) {
        const series = (data.series as Record<string, { value: string | null }[]>)[
          metric
        ];
        const v = series?.[idx]?.value;
        row[metric] = v != null ? Number(v) : null;
      }
      return row;
    }) ?? [];

  const empty =
    !isLoading &&
    rows.length > 0 &&
    rows.every((r) => METRICS.every((m) => r[m] == null));

  return (
    <ChartCard
      title="Revenue, Gross Margin, EBITDA"
      subtitle="Last 24 months (₹ Lacs)"
      loading={isLoading}
      error={error ? "Could not load time series." : undefined}
      empty={empty || rows.length === 0}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          {METRICS.map((metric, idx) => (
            <Line
              key={metric}
              type="monotone"
              dataKey={metric}
              stroke={CHART_PALETTE[idx]}
              dot={false}
              connectNulls
              name={METRIC_LABELS[metric] ?? metric}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
