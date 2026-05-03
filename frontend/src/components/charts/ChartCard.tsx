import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
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
    <Paper elevation={1} sx={{ p: 2 }}>
      <Stack spacing={0.5} sx={{ mb: 1 }}>
        <Typography variant="subtitle1" component="h3">
          {title}
        </Typography>
        {subtitle && (
          <Typography variant="caption" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </Stack>
      <Box sx={{ height, position: "relative" }}>
        {loading ? (
          <Stack
            alignItems="center"
            justifyContent="center"
            sx={{ height: "100%" }}
          >
            <CircularProgress size={24} />
          </Stack>
        ) : error ? (
          <Stack
            alignItems="center"
            justifyContent="center"
            sx={{ height: "100%" }}
          >
            <Typography color="error">{error}</Typography>
          </Stack>
        ) : empty ? (
          <Stack
            alignItems="center"
            justifyContent="center"
            sx={{ height: "100%" }}
          >
            <Typography color="text.secondary">{emptyMessage}</Typography>
          </Stack>
        ) : (
          children
        )}
      </Box>
    </Paper>
  );
}
