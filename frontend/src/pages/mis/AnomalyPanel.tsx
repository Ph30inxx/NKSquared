import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import Alert from "@mui/material/Alert";
import Chip from "@mui/material/Chip";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { MisAnomaly, useMisAnomalies } from "../../api/mis";

interface Props {
  submissionId: number;
  hasFile: boolean;
}

const RULE_LABELS: Record<string, string> = {
  MOM_REVENUE_SWING: "MoM revenue swing",
  MOM_EBITDA_FLIP: "MoM EBITDA flip",
  GM_DRIFT: "Gross margin drift",
  MISSING_REQUIRED_LINE: "Missing required line",
  ARITHMETIC_GP: "Arithmetic check",
  CHANNEL_SUM_MISMATCH: "Channel sum mismatch",
  FX_RATE_STALE: "FX rate stale",
  FUTURE_DATED_ROW: "Future-dated row",
  DUPLICATE_SUBMISSION: "Duplicate submission",
  UNIT_MISMATCH: "Unit mismatch",
};

function periodChip(a: MisAnomaly): string | null {
  if (a.period_year == null || a.period_month == null) return null;
  return new Date(a.period_year, a.period_month - 1, 1).toLocaleString("en-IN", {
    month: "short",
    year: "numeric",
  });
}

function AnomalyRow({ a }: { a: MisAnomaly }) {
  const isError = a.severity === "error";
  return (
    <ListItem
      alignItems="flex-start"
      sx={{
        borderLeft: 3,
        borderColor: isError ? "error.main" : "warning.main",
        pl: 2,
        bgcolor: "background.default",
      }}
    >
      <ListItemIcon sx={{ minWidth: 36, mt: 0.5 }}>
        {isError ? (
          <ErrorOutlineIcon color="error" />
        ) : (
          <WarningAmberIcon color="warning" />
        )}
      </ListItemIcon>
      <ListItemText
        primary={
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            <Typography variant="subtitle2">
              {RULE_LABELS[a.rule_code] ?? a.rule_code}
            </Typography>
            {periodChip(a) && (
              <Chip size="small" label={periodChip(a)} variant="outlined" />
            )}
            {a.geography && (
              <Chip size="small" label={a.geography} variant="outlined" />
            )}
            {a.bu_id && (
              <Chip size="small" label={`BU ${a.bu_id}`} variant="outlined" />
            )}
          </Stack>
        }
        secondary={
          <Typography variant="body2" color="text.secondary">
            {a.message}
          </Typography>
        }
      />
    </ListItem>
  );
}

export default function AnomalyPanel({ submissionId, hasFile }: Props) {
  const { data, isLoading, isError } = useMisAnomalies(hasFile ? submissionId : null);

  if (!hasFile) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6" gutterBottom>
          Anomalies
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Upload a file to run anomaly checks.
        </Typography>
      </Paper>
    );
  }

  if (isLoading) return null;

  if (isError) {
    return (
      <Paper sx={{ p: 3 }}>
        <Typography variant="h6">Anomalies</Typography>
        <Alert severity="error" sx={{ mt: 1 }}>
          Could not load anomalies.
        </Alert>
      </Paper>
    );
  }

  const anomalies = data ?? [];
  const errors = anomalies.filter((a) => a.severity === "error");
  const warnings = anomalies.filter((a) => a.severity === "warning");

  return (
    <Paper sx={{ p: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" mb={1}>
        <Typography variant="h6">Anomalies</Typography>
        {errors.length > 0 && (
          <Chip
            size="small"
            color="error"
            label={`${errors.length} error${errors.length > 1 ? "s" : ""}`}
          />
        )}
        {warnings.length > 0 && (
          <Chip
            size="small"
            color="warning"
            label={`${warnings.length} warning${warnings.length > 1 ? "s" : ""}`}
          />
        )}
      </Stack>
      {anomalies.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          No anomalies detected.
        </Typography>
      ) : (
        <List disablePadding sx={{ "& > li + li": { mt: 1 } }}>
          {[...errors, ...warnings].map((a) => (
            <AnomalyRow key={a.id} a={a} />
          ))}
        </List>
      )}
    </Paper>
  );
}
