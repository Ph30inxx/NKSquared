import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompanySummary } from "../../../api/timeseries";
import ChartCard from "../../../components/charts/ChartCard";

interface Props {
  companyCode: string;
}

interface WaterfallRow {
  label: string;
  base: number;
  delta: number;
  color: string;
}

const POSITIVE = "#2e7d32";
const NEGATIVE = "#d32f2f";
const TOTAL = "#1976d2";

export default function PnlWaterfallChart({ companyCode }: Props) {
  const { data, isLoading, error } = useCompanySummary(companyCode);

  const steps = data?.waterfall ?? [];
  const rows: WaterfallRow[] = [];
  let running = 0;
  for (const step of steps) {
    const v = step.value != null ? Number(step.value) : 0;
    if (step.kind === "total" || step.kind === "subtotal") {
      // Bars that show the absolute level — base = 0.
      rows.push({
        label: step.label,
        base: 0,
        delta: v,
        color: TOTAL,
      });
      running = v;
    } else {
      // Delta bars stack on top of the running total.
      const next = running + v;
      const base = Math.min(running, next);
      const delta = Math.abs(v);
      rows.push({
        label: step.label,
        base,
        delta,
        color: v >= 0 ? POSITIVE : NEGATIVE,
      });
      running = next;
    }
  }

  const month = data?.latest_month
    ? new Date(data.latest_month).toLocaleString("en-IN", {
        month: "long",
        year: "numeric",
      })
    : "";

  return (
    <ChartCard
      title="P&L waterfall"
      subtitle={month ? `${month} (₹ Lacs)` : "Latest month (₹ Lacs)"}
      loading={isLoading}
      error={error ? "No summary available yet." : undefined}
      empty={!isLoading && rows.length === 0}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis />
          <Tooltip
            formatter={(_, _name, item) => {
              const r = item.payload as WaterfallRow;
              const total = r.base + r.delta;
              return [`${total.toFixed(1)} L`, r.label];
            }}
          />
          <Bar dataKey="base" stackId="a" fill="transparent" />
          <Bar dataKey="delta" stackId="a">
            {rows.map((r, idx) => (
              <Cell key={idx} fill={r.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
