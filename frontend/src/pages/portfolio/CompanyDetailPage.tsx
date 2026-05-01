import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Grid from "@mui/material/Grid";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
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
  useCompany,
  useCompanyTransactions,
  useDeleteTransaction,
  useSoftDeleteCompany,
} from "../../api/companies";
import { formatCr, formatDate, formatMoic, moicColor } from "../../utils/format";
import CompanyFormDialog from "./CompanyFormDialog";
import TransactionFormDialog from "./TransactionFormDialog";

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
  const softDelete = useSoftDeleteCompany();
  const deleteTxn = useDeleteTransaction(companyId ?? 0);

  const [editOpen, setEditOpen] = useState(false);
  const [txnDialogOpen, setTxnDialogOpen] = useState(false);
  const [editingTxn, setEditingTxn] = useState<Transaction | null>(null);

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
        <Typography variant="h6" gutterBottom>
          MOIC
        </Typography>
        <Grid container spacing={3}>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Invested (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(summary.invested)}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Realized (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(summary.realized)}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              Current (₹Cr)
            </Typography>
            <Typography variant="h5">{formatCr(c.current_value_cr)}</Typography>
          </Grid>
          <Grid item xs={6} sm={3}>
            <Typography variant="caption" color="text.secondary">
              MOIC
            </Typography>
            <Typography variant="h5" sx={{ color: moicColor(c.moic) }}>
              {formatMoic(c.moic)}
            </Typography>
          </Grid>
        </Grid>
        {summary.skipped.length > 0 && (
          <Alert severity="info" sx={{ mt: 2 }}>
            {summary.skipped.length} transaction(s) skipped from MOIC because they have no INR
            amount yet (non-INR with no FX rate). Sprint 3 will resolve these automatically.
          </Alert>
        )}
      </Paper>

      <Paper>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="center"
          sx={{ p: 2 }}
        >
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
    </Stack>
  );
}
