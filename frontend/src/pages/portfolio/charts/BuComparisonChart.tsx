import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useCompanySummary } from "../../../api/timeseries";
import ChartCard from "../../../components/charts/ChartCard";
import { CHART_PALETTE } from "../../../components/charts/chartPalette";

interface Props {
  companyCode: string;
}

export default function BuComparisonChart({ companyCode }: Props) {
  const { data, isLoading, error } = useCompanySummary(companyCode);
  const rows =
    data?.bu_breakdown.map((b) => ({
      bu_id: b.bu_id ?? "—",
      revenue_lacs: b.revenue_lacs ? Number(b.revenue_lacs) : 0,
      gross_margin_lacs: b.gross_margin_lacs ? Number(b.gross_margin_lacs) : 0,
      ebitda_lacs: b.ebitda_lacs ? Number(b.ebitda_lacs) : 0,
    })) ?? [];

  return (
    <ChartCard
      title="Business unit comparison"
      subtitle="Revenue, GP, EBITDA per BU (latest month, ₹ Lacs)"
      loading={isLoading}
      error={error ? "No summary available yet." : undefined}
      empty={!isLoading && rows.length === 0}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="bu_id" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="revenue_lacs" name="Revenue" fill={CHART_PALETTE[0]} />
          <Bar
            dataKey="gross_margin_lacs"
            name="Gross Margin"
            fill={CHART_PALETTE[2]}
          />
          <Bar dataKey="ebitda_lacs" name="EBITDA" fill={CHART_PALETTE[1]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
