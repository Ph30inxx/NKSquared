import { useEffect, useState, type FormEvent } from "react";
import Alert from "@mui/material/Alert";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";

import {
  TRANSACTION_TYPES,
  Transaction,
  TransactionType,
  TransactionWritePayload,
  useCreateTransaction,
  useUpdateTransaction,
} from "../../api/companies";

interface TransactionFormDialogProps {
  companyId: number;
  open: boolean;
  onClose: () => void;
  initial?: Transaction | null;
}

interface FormState {
  transaction_date: string;
  transaction_type: TransactionType;
  amount: string;
  currency: string;
  fx_rate_used: string;
  series: string;
  instrument_type: string;
  notes: string;
}

const EMPTY: FormState = {
  transaction_date: new Date().toISOString().slice(0, 10),
  transaction_type: "Investment",
  amount: "",
  currency: "INR",
  fx_rate_used: "",
  series: "",
  instrument_type: "",
  notes: "",
};

function txnToForm(t: Transaction): FormState {
  return {
    transaction_date: t.transaction_date,
    transaction_type: t.transaction_type as TransactionType,
    amount: t.original_amount ?? "",
    currency: t.original_currency,
    fx_rate_used: t.fx_rate_used ?? "",
    series: t.series ?? "",
    instrument_type: t.instrument_type ?? "",
    notes: t.notes ?? "",
  };
}

export default function TransactionFormDialog({
  companyId,
  open,
  onClose,
  initial,
}: TransactionFormDialogProps) {
  const isEdit = Boolean(initial);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const createMut = useCreateTransaction(companyId);
  const updateMut = useUpdateTransaction(companyId);

  useEffect(() => {
    setForm(initial ? txnToForm(initial) : EMPTY);
    setError(null);
  }, [initial, open]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.amount && form.transaction_type !== "Write_off" && form.transaction_type !== "Write_down") {
      setError("Amount is required");
      return;
    }
    // Non-INR no longer requires a manual rate — the backend looks one up from forex_rates.
    // If no rate is found, the row is saved with amount_inr_cr=null and the analyst can
    // resolve it later via "Recompute FX rates" on the company detail page.
    const payload: TransactionWritePayload = {
      transaction_date: form.transaction_date,
      transaction_type: form.transaction_type,
      amount: form.amount || "0",
      currency: form.currency || "INR",
      fx_rate_used: form.fx_rate_used || null,
      series: form.series || null,
      instrument_type: form.instrument_type || null,
      notes: form.notes || null,
    };
    try {
      if (isEdit && initial) {
        await updateMut.mutateAsync({ id: initial.id, payload });
      } else {
        await createMut.mutateAsync(payload);
      }
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setError(typeof detail === "string" ? detail : "Save failed");
    }
  }

  const submitting = createMut.isPending || updateMut.isPending;
  const isNonInr = form.currency.toUpperCase() !== "INR";

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit}>
        <DialogTitle>{isEdit ? "Edit transaction" : "Add transaction"}</DialogTitle>
        <DialogContent dividers>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Date"
                type="date"
                value={form.transaction_date}
                onChange={(e) => update("transaction_date", e.target.value)}
                InputLabelProps={{ shrink: true }}
                required
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Type"
                select
                value={form.transaction_type}
                onChange={(e) => update("transaction_type", e.target.value as TransactionType)}
                fullWidth
                required
              >
                {TRANSACTION_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Amount (positive)"
                type="number"
                value={form.amount}
                onChange={(e) => update("amount", e.target.value)}
                inputProps={{ step: "0.0001", min: "0" }}
                helperText="Backend signs by type (Investment → outflow, Exit → inflow)"
                fullWidth
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <TextField
                label="Currency"
                value={form.currency}
                onChange={(e) => update("currency", e.target.value.toUpperCase())}
                inputProps={{ maxLength: 10 }}
                fullWidth
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <TextField
                label="FX rate"
                type="number"
                value={form.fx_rate_used}
                onChange={(e) => update("fx_rate_used", e.target.value)}
                inputProps={{ step: "0.000001", min: "0" }}
                disabled={!isNonInr}
                helperText={
                  isNonInr ? "Leave blank to look up daily rate" : "INR is 1:1"
                }
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Series"
                value={form.series}
                onChange={(e) => update("series", e.target.value)}
                placeholder="Series B"
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Instrument"
                value={form.instrument_type}
                onChange={(e) => update("instrument_type", e.target.value)}
                placeholder="CCPS / Equity / CCD"
                fullWidth
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Notes"
                value={form.notes}
                onChange={(e) => update("notes", e.target.value)}
                multiline
                minRows={2}
                fullWidth
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Add transaction"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
