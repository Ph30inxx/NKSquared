import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import {
  Transaction,
  useCompanyTransactions,
} from "../../../api/companies";
import { formatCr, formatDate } from "../../../utils/format";

interface Props {
  companyId: number;
}

const CASH_OUTFLOW = new Set(["Investment", "Follow_on"]);
const CASH_INFLOW = new Set(["Partial_exit", "Full_exit", "Distribution"]);

function colorFor(t: Transaction): "primary" | "success" | "warning" | "default" {
  if (CASH_OUTFLOW.has(t.transaction_type)) return "primary";
  if (CASH_INFLOW.has(t.transaction_type)) return "success";
  if (t.transaction_type.startsWith("Write")) return "warning";
  return "default";
}

export default function InvestmentTimeline({ companyId }: Props) {
  const { data: txns, isLoading } = useCompanyTransactions(companyId);

  if (isLoading) {
    return (
      <Paper elevation={1} sx={{ p: 2 }}>
        <Typography variant="subtitle1">Investment timeline</Typography>
        <Typography variant="caption" color="text.secondary">
          Loading…
        </Typography>
      </Paper>
    );
  }

  const sorted = [...(txns ?? [])].sort(
    (a, b) => Date.parse(a.transaction_date) - Date.parse(b.transaction_date),
  );

  return (
    <Paper elevation={1} sx={{ p: 2 }}>
      <Typography variant="subtitle1" component="h3" sx={{ mb: 1.5 }}>
        Investment timeline
      </Typography>
      {sorted.length === 0 ? (
        <Typography color="text.secondary">No transactions yet.</Typography>
      ) : (
        <Stack spacing={1.5}>
          {sorted.map((t) => (
            <Stack
              key={t.id}
              direction="row"
              spacing={2}
              alignItems="center"
            >
              <Box sx={{ minWidth: 110 }}>
                <Typography variant="caption" color="text.secondary">
                  {formatDate(t.transaction_date)}
                </Typography>
              </Box>
              <Chip
                label={t.transaction_type.replace(/_/g, " ")}
                color={colorFor(t)}
                size="small"
              />
              <Typography variant="body2" sx={{ flexGrow: 1 }}>
                {t.series ? `${t.series} · ` : ""}
                {t.instrument_type ?? ""}
              </Typography>
              <Typography variant="body2" sx={{ fontFamily: "monospace" }}>
                {t.amount_inr_cr ? `₹${formatCr(t.amount_inr_cr)} Cr` : "—"}
              </Typography>
            </Stack>
          ))}
        </Stack>
      )}
    </Paper>
  );
}
