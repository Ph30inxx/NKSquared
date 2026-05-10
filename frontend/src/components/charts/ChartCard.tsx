import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

interface ChartCardProps {
  title: string;
  subtitle?: string;
  height?: number;
  loading?: boolean;
  error?: string | null;
  empty?: boolean;
  emptyMessage?: string;
  children: React.ReactNode;
}

export default function ChartCard({
  title,
  subtitle,
  height = 300,
  loading,
  error,
  empty,
  emptyMessage = "No data yet.",
  children,
}: ChartCardProps) {
  return (
    <Paper sx={{ overflow: "hidden" }}>
      <Box sx={{ px: 2.5, py: 2 }}>
        <Typography variant="subtitle2" component="h3" sx={{ fontWeight: 700 }}>
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Box>
      <Divider />
      <Box sx={{ height, position: "relative", p: 1 }}>
        {loading ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: "100%" }}>
            <CircularProgress size={28} />
          </Stack>
        ) : error ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: "100%" }}>
            <Typography color="error" variant="body2">{error}</Typography>
          </Stack>
        ) : empty ? (
          <Stack alignItems="center" justifyContent="center" sx={{ height: "100%" }}>
            <Typography color="text.secondary" variant="body2">{emptyMessage}</Typography>
          </Stack>
        ) : (
          children
        )}
      </Box>
    </Paper>
  );
}
