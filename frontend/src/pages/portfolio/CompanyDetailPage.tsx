import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Snackbar from "@mui/material/Snackbar";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

import {
  Transaction,
  Valuation,
  useCompany,
  useCompanyTransactions,
  useCompanyValuations,
  useDeleteTransaction,
  useDeleteValuation,
  useMarkCurrent,
  useRecomputeFx,
  useSoftDeleteCompany,
} from "../../api/companies";
import {
  formatCr,
  formatDate,
  formatMoic,
  formatPct,
  moicColor,
} from "../../utils/format";
import { useSendReminderNow } from "../../api/reminders";
import CompanyFormDialog from "./CompanyFormDialog";
import TransactionFormDialog from "./TransactionFormDialog";
import ValuationFormDialog from "./ValuationFormDialog";
import BuComparisonChart from "./charts/BuComparisonChart";
import ChannelMixChart from "./charts/ChannelMixChart";
import InvestmentTimeline from "./charts/InvestmentTimeline";
import PnlWaterfallChart from "./charts/PnlWaterfallChart";
import RevenueTimeseriesChart from "./charts/RevenueTimeseriesChart";

const NEGATIVE_TYPES = new Set(["Investment", "Follow_on"]);
const POSITIVE_TYPES = new Set(["Partial_exit", "Full_exit", "Distribution"]);

function deriveSummary(transactions: Transaction[] | undefined, currentCr: string | null) {
  const skipped: number[] = [];
  let invested = 0;
  let realized = 0;
  for (const t of transactions ?? []) {
    if (t.amount_inr_cr == null) {
      skipped.push(t.id);
      continue;
    }
    const amt = Number(t.amount_inr_cr);
    if (NEGATIVE_TYPES.has(t.transaction_type)) invested += Math.abs(amt);
    else if (POSITIVE_TYPES.has(t.transaction_type)) realized += amt;
  }
  const current = currentCr != null ? Number(currentCr) : 0;
  return { invested, realized, current, skipped };
}

interface MetadataRowProps {
  label: string;
  value: string | null | undefined;
}

function MetadataRow({ label, value }: MetadataRowProps) {
  return (
    <Stack spacing={0.5}>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
      <Typography variant="body2">{value || "—"}</Typography>
    </Stack>
  );
}

export default function CompanyDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const companyId = params.id ? Number(params.id) : null;

  const company = useCompany(companyId);
  const txns = useCompanyTransactions(companyId);
  const vals = useCompanyValuations(companyId);
  const softDelete = useSoftDeleteCompany();
  const deleteTxn = useDeleteTransaction(companyId ?? 0);
  const deleteValuation = useDeleteValuation(companyId ?? 0);
  const markCurrent = useMarkCurrent(companyId ?? 0);
  const recomputeFx = useRecomputeFx(companyId ?? 0);

  const [editOpen, setEditOpen] = useState(false);
  const [txnDialogOpen, setTxnDialogOpen] = useState(false);
  const [editingTxn, setEditingTxn] = useState<Transaction | null>(null);
  const [valDialogOpen, setValDialogOpen] = useState(false);
  const [recomputeMessage, setRecomputeMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [reminderToast, setReminderToast] = useState<{
    severity: "success" | "error";
    message: string;
  } | null>(null);
  const sendReminder = useSendReminderNow();

  if (companyId == null) {
    return <Alert severity="error">Missing company id.</Alert>;
  }

  if (company.isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }
  if (company.isError || !company.data) {
    return <Alert severity="error">Could not load company.</Alert>;
  }

  const c = company.data;
  const summary = deriveSummary(txns.data, c.current_value_cr);

  async function handleSoftDelete() {
    if (!confirm(`Mark ${c.display_name || c.company_name} inactive?`)) return;
    await softDelete.mutateAsync(c.id);
    navigate("/portfolio");
  }

  async function handleDeleteTxn(txn: Transaction) {
    if (!confirm("Delete this transaction?")) return;
    await deleteTxn.mutateAsync(txn.id);
  }

  async function handleDeleteValuation(v: Valuation) {
    if (!confirm("Delete this valuation?")) return;
    await deleteValuation.mutateAsync(v.id);
  }

  async function handleMarkCurrent(v: Valuation) {
    setActionError(null);
    try {
      await markCurrent.mutateAsync(v.id);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setActionError(typeof detail === "string" ? detail : "Mark-current failed");
    }
  }

  async function handleSendReminderNow() {
    try {
      const log = await sendReminder.mutateAsync({ companyId: c.id });
      setReminderToast({
        severity: log.status === "Sent" ? "success" : "error",
        message:
          log.status === "Sent"
            ? `Reminder sent to ${log.recipient_email}.`
            : `Reminder failed: ${log.subject ?? log.status}`,
      });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setReminderToast({
        severity: "error",
        message: typeof detail === "string" ? detail : "Could not send reminder.",
      });
    }
  }

  async function handleRecomputeFx() {
    setActionError(null);
    setRecomputeMessage(null);
    try {
      const res = await recomputeFx.mutateAsync();
      setRecomputeMessage(
        `Updated ${res.updated} transaction(s); ${res.still_unresolved} still without an FX rate.`,
      );
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setActionError(typeof detail === "string" ? detail : "Recompute failed");
    }
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" spacing={1} alignItems="center">
        <IconButton onClick={() => navigate("/portfolio")} size="small">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4" component="h1">
          {c.display_name || c.company_name}
        </Typography>
        {!c.is_active && <Chip label="Inactive" color="warning" size="small" />}
        <Box flexGrow={1} />
        <Button
          startIcon={<SendIcon />}
          onClick={handleSendReminderNow}
          disabled={sendReminder.isPending || !c.is_active}
        >
          {sendReminder.isPending ? "Sending…" : "Send reminder now"}
        </Button>
        <Button startIcon={<EditIcon />} onClick={() => setEditOpen(true)}>
          Edit
        </Button>
        <Button
          startIcon={<DeleteIcon />}
          color="error"
          onClick={handleSoftDelete}
          disabled={!c.is_active}
        >
          Delete
        </Button>
      </Stack>
      <Snackbar
        open={!!reminderToast}
        autoHideDuration={6000}
        onClose={() => setReminderToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        {reminderToast ? (
          <Alert
            severity={reminderToast.severity}
            onClose={() => setReminderToast(null)}
            sx={{ width: "100%" }}
          >
            {reminderToast.message}
          </Alert>
        ) : undefined}
      </Snackbar>

      {actionError && <Alert severity="error">{actionError}</Alert>}

      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Sector" value={c.sector} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Sub-sector" value={c.sub_sector} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Vehicle" value={c.portfolio_type?.replace(/_/g, " ")} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Asset class" value={c.asset_class?.replace(/_/g, " ")} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Country" value={c.country} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Status" value={c.investment_status?.replace(/_/g, " ")} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="First investment" value={formatDate(c.date_of_first_investment)} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Currency" value={c.currency} />
          </Grid>
          {c.notes && (
            <Grid item xs={12}>
              <MetadataRow label="Notes" value={c.notes} />
            </Grid>
          )}
        </Grid>
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="h6">Performance</Typography>
          {summary.skipped.length > 0 && (
            <Button
              startIcon={<RefreshIcon />}
              onClick={handleRecomputeFx}
              disabled={recomputeFx.isPending}
              size="small"
            >
              {recomputeFx.isPending ? "Recomputing…" : "Recompute FX rates"}
            </Button>
          )}
        </Stack>
        <Grid container spacing={3}>
          <Grid item xs={6} sm={2.4}>
            <Typography variant="caption" color="text.secondary">
              Invested (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(summary.invested)}</Typography>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Typography variant="caption" color="text.secondary">
              Realized (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(summary.realized)}</Typography>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Typography variant="caption" color="text.secondary">
              Current (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(c.current_value_cr)}</Typography>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Typography variant="caption" color="text.secondary">
              MOIC
            </Typography>
            <Typography variant="h5" sx={{ color: moicColor(c.moic) }}>
              {formatMoic(c.moic)}
            </Typography>
          </Grid>
          <Grid item xs={6} sm={2.4}>
            <Typography variant="caption" color="text.secondary">
              IRR
            </Typography>
            <Typography variant="h5">{formatPct(c.irr)}</Typography>
          </Grid>
        </Grid>
        {recomputeMessage && (
          <Alert severity="info" sx={{ mt: 2 }} onClose={() => setRecomputeMessage(null)}>
            {recomputeMessage}
          </Alert>
        )}
        {summary.skipped.length > 0 && !recomputeMessage && (
          <Alert severity="info" sx={{ mt: 2 }}>
            {summary.skipped.length} transaction(s) skipped from MOIC because they have no INR
            amount yet (non-INR with no FX rate). Add a rate via the FX rates page, then click
            <strong> Recompute FX rates </strong> above.
          </Alert>
        )}
      </Paper>

      {c.company_code ? (
        <Stack spacing={2}>
          <Typography variant="h6">MIS analytics</Typography>
          <Grid container spacing={2}>
            <Grid item xs={12} lg={6}>
              <RevenueTimeseriesChart companyCode={c.company_code} />
            </Grid>
            <Grid item xs={12} lg={6}>
              <ChannelMixChart companyCode={c.company_code} />
            </Grid>
            <Grid item xs={12} lg={6}>
              <PnlWaterfallChart companyCode={c.company_code} />
            </Grid>
            <Grid item xs={12} lg={6}>
              <BuComparisonChart companyCode={c.company_code} />
            </Grid>
            <Grid item xs={12}>
              <InvestmentTimeline companyId={c.id} />
            </Grid>
          </Grid>
        </Stack>
      ) : (
        <Alert severity="info">
          No MIS analytics yet — link this company to its MIS code to surface
          time-series, channel mix, and BU comparisons here.
        </Alert>
      )}

      <Paper>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2 }}>
          <Typography variant="h6">Valuations</Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setValDialogOpen(true)}
          >
            Add valuation
          </Button>
        </Stack>
        {vals.isLoading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Source</TableCell>
                  <TableCell align="right">Post-money</TableCell>
                  <TableCell align="right">Pre-money</TableCell>
                  <TableCell>Currency</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell align="right" />
                </TableRow>
              </TableHead>
              <TableBody>
                {vals.data?.map((v) => (
                  <TableRow key={v.id}>
                    <TableCell>{formatDate(v.valuation_date)}</TableCell>
                    <TableCell>{v.source ?? "—"}</TableCell>
                    <TableCell align="right">{formatCr(v.post_money_valuation_cr)}</TableCell>
                    <TableCell align="right">{formatCr(v.pre_money_valuation_cr)}</TableCell>
                    <TableCell>{v.currency}</TableCell>
                    <TableCell>{v.notes ?? ""}</TableCell>
                    <TableCell align="right">
                      <Tooltip title="Use this as current value (pro-rata)">
                        <span>
                          <IconButton
                            size="small"
                            color="primary"
                            onClick={() => handleMarkCurrent(v)}
                            disabled={markCurrent.isPending}
                          >
                            <CheckCircleIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <IconButton size="small" onClick={() => handleDeleteValuation(v)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {vals.data && vals.data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7}>
                      <Box py={3} textAlign="center" color="text.secondary">
                        No valuations recorded. Click <strong>Add valuation</strong> above.
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Paper>
        <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ p: 2 }}>
          <Typography variant="h6">Transactions</Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => {
              setEditingTxn(null);
              setTxnDialogOpen(true);
            }}
          >
            Add transaction
          </Button>
        </Stack>
        {txns.isLoading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Series</TableCell>
                  <TableCell align="right">Amount</TableCell>
                  <TableCell>Currency</TableCell>
                  <TableCell align="right">INR (Cr)</TableCell>
                  <TableCell>Notes</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {txns.data?.map((t) => (
                  <TableRow key={t.id}>
                    <TableCell>{formatDate(t.transaction_date)}</TableCell>
                    <TableCell>{t.transaction_type.replace(/_/g, " ")}</TableCell>
                    <TableCell>{t.series ?? "—"}</TableCell>
                    <TableCell align="right">{formatCr(t.original_amount)}</TableCell>
                    <TableCell>{t.original_currency}</TableCell>
                    <TableCell align="right">
                      {t.amount_inr_cr ? (
                        formatCr(t.amount_inr_cr)
                      ) : (
                        <Tooltip title="Awaiting FX rate">
                          <span>—</span>
                        </Tooltip>
                      )}
                    </TableCell>
                    <TableCell>{t.notes ?? ""}</TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={() => {
                          setEditingTxn(t);
                          setTxnDialogOpen(true);
                        }}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => handleDeleteTxn(t)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {txns.data && txns.data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Box py={3} textAlign="center" color="text.secondary">
                        No transactions yet. Click <strong>Add transaction</strong> above.
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <CompanyFormDialog
        open={editOpen}
        onClose={() => setEditOpen(false)}
        initial={c}
      />

      <TransactionFormDialog
        companyId={c.id}
        open={txnDialogOpen}
        onClose={() => {
          setTxnDialogOpen(false);
          setEditingTxn(null);
        }}
        initial={editingTxn}
      />

      <ValuationFormDialog
        companyId={c.id}
        open={valDialogOpen}
        onClose={() => setValDialogOpen(false)}
      />
    </Stack>
  );
}
