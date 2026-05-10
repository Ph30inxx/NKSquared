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
import Box from "@mui/material/Box";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Skeleton from "@mui/material/Skeleton";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import AccountBalanceIcon from "@mui/icons-material/AccountBalance";
import BusinessCenterIcon from "@mui/icons-material/BusinessCenter";
import ShowChartIcon from "@mui/icons-material/ShowChart";
import PendingActionsIcon from "@mui/icons-material/PendingActions";

import { useDashboardOverview } from "../api/portfolio";
import ChartCard from "../components/charts/ChartCard";
import { CHART_PALETTE, colorFor } from "../components/charts/chartPalette";
import { formatCr, formatMoic } from "../utils/format";
import type { SvgIconComponent } from "@mui/icons-material";

interface KpiProps {
  label: string;
  value: string;
  helpText?: string;
  Icon: SvgIconComponent;
  accent: string;
}

function KpiCard({ label, value, helpText, Icon, accent }: KpiProps) {
  return (
    <Paper
      sx={{
        p: 2.5,
        height: "100%",
        borderLeft: `4px solid ${accent}`,
        display: "flex",
        alignItems: "flex-start",
        gap: 2,
      }}
    >
      <Box
        sx={{
          width: 40,
          height: 40,
          borderRadius: 2,
          bgcolor: `${accent}18`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <Icon sx={{ fontSize: 20, color: accent }} />
      </Box>
      <Stack spacing={0.25} sx={{ minWidth: 0 }}>
        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em" }}>
          {label}
        </Typography>
        <Typography variant="h5" sx={{ fontWeight: 800, lineHeight: 1.1, letterSpacing: "-0.02em" }}>
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

function KpiSkeleton() {
  return (
    <Paper sx={{ p: 2.5, height: "100%" }}>
      <Stack spacing={1}>
        <Skeleton variant="rectangular" width={100} height={14} sx={{ borderRadius: 1 }} />
        <Skeleton variant="rectangular" width={140} height={32} sx={{ borderRadius: 1 }} />
        <Skeleton variant="rectangular" width={80} height={12} sx={{ borderRadius: 1 }} />
      </Stack>
    </Paper>
  );
}

const KPI_ACCENTS = ["#1B4FD8", "#059669", "#D97706", "#7C3AED", "#DC2626"];

export default function Dashboard() {
  const { data, isLoading, error } = useDashboardOverview();

  if (error) {
    return (
      <Alert severity="error" sx={{ maxWidth: 500 }}>
        Couldn't load the dashboard. Please refresh the page.
      </Alert>
    );
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

  const kpis = [
    {
      label: "Total Invested",
      value: `₹${formatCr(summary?.total_invested_cr)} Cr`,
      helpText: `${summary?.company_count ?? 0} active companies`,
      Icon: AccountBalanceIcon,
      accent: KPI_ACCENTS[0],
    },
    {
      label: "Current Value",
      value: `₹${formatCr(summary?.current_value_cr)} Cr`,
      Icon: TrendingUpIcon,
      accent: KPI_ACCENTS[1],
    },
    {
      label: "Weighted MOIC",
      value: formatMoic(summary?.weighted_moic ?? null),
      Icon: ShowChartIcon,
      accent: KPI_ACCENTS[2],
    },
    {
      label: "Companies",
      value: String(summary?.company_count ?? 0),
      Icon: BusinessCenterIcon,
      accent: KPI_ACCENTS[3],
    },
    {
      label: "Pending MIS",
      value: String(summary?.pending_mis_count ?? 0),
      helpText: "Pending / Submitted / Under Review",
      Icon: PendingActionsIcon,
      accent: KPI_ACCENTS[4],
    },
  ];

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h4" component="h1">
            Portfolio Overview
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Consolidated view across all investments
          </Typography>
        </Box>
      </Stack>

      <Grid container spacing={2}>
        {kpis.map((kpi, i) => (
          <Grid item xs={12} sm={6} md={2.4} key={i}>
            {isLoading ? <KpiSkeleton /> : <KpiCard {...kpi} />}
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <ChartCard
            title="Capital Allocation by Sector"
            subtitle="Sum of invested capital (₹ Cr)"
            loading={isLoading}
            empty={!isLoading && sectorRows.length === 0}
          >
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={sectorRows}
                  dataKey="invested"
                  nameKey="key"
                  innerRadius={65}
                  outerRadius={105}
                  paddingAngle={2}
                >
                  {sectorRows.map((_, idx) => (
                    <Cell key={idx} fill={colorFor(idx)} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => [`₹${formatCr(value)} Cr`, "Invested"]}
                  contentStyle={{ borderRadius: 8, fontSize: 13 }}
                />
                <Legend iconType="circle" iconSize={8} />
              </PieChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12} md={6}>
          <ChartCard
            title="Vintage Year vs MOIC"
            subtitle="Weighted MOIC per vintage cohort"
            loading={isLoading}
            empty={!isLoading && vintageRows.length === 0}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={vintageRows} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
                <XAxis dataKey="key" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number) => [`${value.toFixed(2)}x`, "MOIC"]}
                  contentStyle={{ borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="moic" fill={CHART_PALETTE[0]} radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </Grid>
        <Grid item xs={12}>
          <ChartCard
            title="Capital Allocation by Portfolio Category"
            subtitle="Invested capital (₹ Cr) by entity / vehicle"
            loading={isLoading}
            empty={!isLoading && categoryRows.length === 0}
            height={320}
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={categoryRows}
                layout="vertical"
                margin={{ top: 0, right: 16, left: 16, bottom: 0 }}
              >
                <XAxis type="number" tick={{ fontSize: 12 }} />
                <YAxis dataKey="key" type="category" width={150} tick={{ fontSize: 12 }} />
                <Tooltip
                  formatter={(value: number) => [`₹${formatCr(value)} Cr`, "Invested"]}
                  contentStyle={{ borderRadius: 8, fontSize: 13 }}
                />
                <Bar dataKey="invested" radius={[0, 4, 4, 0]}>
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
