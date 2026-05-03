import {
  Bar,
  BarChart,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import Alert from "@mui/material/Alert";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { useDashboardOverview } from "../api/portfolio";
import ChartCard from "../components/charts/ChartCard";
import { CHART_PALETTE, colorFor } from "../components/charts/chartPalette";
import { formatCr, formatMoic } from "../utils/format";

interface KpiProps {
  label: string;
  value: string;
  helpText?: string;
}

function KpiCard({ label, value, helpText }: KpiProps) {
  return (
    <Paper elevation={1} sx={{ p: 2, height: "100%" }}>
      <Stack spacing={0.5}>
        <Typography variant="caption" color="text.secondary">
          {label}
        </Typography>
        <Typography variant="h5" component="div" sx={{ fontWeight: 600 }}>
          {value}
        </Typography>
        {helpText && (
          <Typography variant="caption" color="text.secondary">
            {helpText}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useDashboardOverview();

  if (error) {
    return <Alert severity="error">Couldn’t load the dashboard.</Alert>;
  }

  const summary = data?.summary;
  const sectorRows = (data?.by_sector ?? []).map((b) => ({
    ...b,
    invested: Number(b.invested_cr),
    moic: b.weighted_moic ? Number(b.weighted_moic) : null,
  }));
  const vintageRows = (data?.by_vintage ?? []).map((b) => ({
    ...b,
    invested: Number(b.invested_cr),
    moic: b.weighted_moic ? Number(b.weighted_moic) : 0,
  }));
  const categoryRows = (data?.by_category ?? []).map((b) => ({
    ...b,
    invested: Number(b.invested_cr),
    moic: b.weighted_moic ? Number(b.weighted_moic) : null,
  }));

  return (
    <Stack spacing={3}>
      <Typography variant="h4" component="h1">
        Portfolio overview
      </Typography>

      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={2.4}>
          {isLoading ? (
            <Skeleton variant="rectangular" height={92} />
          ) : (
            <KpiCard
              label="Total invested"
              value={`₹${formatCr(summary?.total_invested_cr)} Cr`}
              helpText={`${summary?.company_count ?? 0} active companies`}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          {isLoading ? (
            <Skeleton variant="rectangular" height={92} />
          ) : (
            <KpiCard
              label="Current value"
              value={`₹${formatCr(summary?.current_value_cr)} Cr`}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          {isLoading ? (
            <Skeleton variant="rectangular" height={92} />
          ) : (
            <KpiCard
              label="Weighted MOIC"
              value={formatMoic(summary?.weighted_moic ?? null)}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          {isLoading ? (
            <Skeleton variant="rectangular" height={92} />
          ) : (
            <KpiCard
              label="Companies"
              value={String(summary?.company_count ?? 0)}
            />
          )}
        </Grid>
        <Grid item xs={12} sm={6} md={2.4}>
          {isLoading ? (
            <Skeleton variant="rectangular" height={92} />
          ) : (
            <KpiCard
              label="Pending MIS"
              value={String(summary?.pending_mis_count ?? 0)}
              helpText="Pending / Submitted / Under Review"
            />
          )}
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <ChartCard
            title="Capital allocation by sector"
            subtitle="Sum of invested capital (INR Cr)"
            loading={isLoading}
            empty={!isLoading && sectorRows.length === 0}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sectorRows}
                  dataKey="invested"
                  nameKey="key"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={1}
                >
                  {sectorRows.map((_, idx) => (
                    <Cell key={idx} fill={colorFor(idx)} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => [`₹${formatCr(value)} Cr`, "Invested"]}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12} md={6}>
          <ChartCard
            title="Vintage year vs MOIC"
            subtitle="Weighted MOIC per vintage cohort"
            loading={isLoading}
            empty={!isLoading && vintageRows.length === 0}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={vintageRows}>
                <XAxis dataKey="key" />
                <YAxis />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(2)}x`, "MOIC"]}
                />
                <Bar dataKey="moic" fill={CHART_PALETTE[0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12}>
          <ChartCard
            title="Capital allocation by portfolio category"
            subtitle="Invested capital (INR Cr) by entity / vehicle"
            loading={isLoading}
            empty={!isLoading && categoryRows.length === 0}
            height={320}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={categoryRows}
                layout="vertical"
                margin={{ left: 80 }}
              >
                <XAxis type="number" />
                <YAxis dataKey="key" type="category" width={140} />
                <Tooltip
                  formatter={(value: number) => [`₹${formatCr(value)} Cr`, "Invested"]}
                />
                <Bar dataKey="invested">
                  {categoryRows.map((_, idx) => (
                    <Cell key={idx} fill={colorFor(idx)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
      </Grid>
    </Stack>
  );
}
