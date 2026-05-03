import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompanyTimeseries } from "../../../api/timeseries";
import ChartCard from "../../../components/charts/ChartCard";
import {
  CHANNEL_LABELS,
  CHART_PALETTE,
} from "../../../components/charts/chartPalette";

interface Props {
  companyCode: string;
}

function fmtMonth(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", { month: "short", year: "2-digit" });
}

export default function ChannelMixChart({ companyCode }: Props) {
  const { data, isLoading, error } = useCompanyTimeseries(companyCode, {
    breakdown: "channels",
  });

  const channels = data ? Object.keys(data.series) : [];
  const rows =
    data?.months.map((m, idx) => {
      const row: Record<string, unknown> = { month: fmtMonth(m) };
      for (const ch of channels) {
        const series = (data.series as Record<string, { value: string | null }[]>)[
          ch
        ];
        const v = series?.[idx]?.value;
        row[ch] = v != null ? Number(v) : 0;
      }
      return row;
    }) ?? [];

  const hasAny = rows.some((r) =>
    channels.some((c) => Number(r[c]) > 0),
  );

  return (
    <ChartCard
      title="Channel mix over time"
      subtitle="Stacked revenue by sales channel (₹ Lacs)"
      loading={isLoading}
      error={error ? "Could not load channel mix." : undefined}
      empty={!isLoading && !hasAny}
    >
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="month" />
          <YAxis />
          <Tooltip />
          <Legend />
          {channels.map((ch, idx) => (
            <Area
              key={ch}
              type="monotone"
              dataKey={ch}
              stackId="1"
              stroke={CHART_PALETTE[idx % CHART_PALETTE.length]}
              fill={CHART_PALETTE[idx % CHART_PALETTE.length]}
              fillOpacity={0.6}
              name={CHANNEL_LABELS[ch] ?? ch}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
