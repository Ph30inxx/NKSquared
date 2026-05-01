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
  VALUATION_SOURCES,
  ValuationWritePayload,
  useCreateValuation,
} from "../../api/companies";

interface ValuationFormDialogProps {
  companyId: number;
  open: boolean;
  onClose: () => void;
}

interface FormState {
  valuation_date: string;
  source: string;
  post_money_valuation_cr: string;
  pre_money_valuation_cr: string;
  currency: string;
  notes: string;
}

const EMPTY: FormState = {
  valuation_date: new Date().toISOString().slice(0, 10),
  source: "Internal",
  post_money_valuation_cr: "",
  pre_money_valuation_cr: "",
  currency: "INR",
  notes: "",
};

export default function ValuationFormDialog({
  companyId,
  open,
  onClose,
}: ValuationFormDialogProps) {
  const [form, setForm] = useState<FormState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const create = useCreateValuation(companyId);

  useEffect(() => {
    if (open) {
      setForm(EMPTY);
      setError(null);
    }
  }, [open]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.post_money_valuation_cr) {
      setError("Post-money valuation is required.");
      return;
    }
    const payload: ValuationWritePayload = {
      valuation_date: form.valuation_date,
      post_money_valuation_cr: form.post_money_valuation_cr,
      pre_money_valuation_cr: form.pre_money_valuation_cr || null,
      currency: form.currency || "INR",
      source: form.source || null,
      notes: form.notes || null,
    };
    try {
      await create.mutateAsync(payload);
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setError(typeof detail === "string" ? detail : "Save failed");
    }
  }

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit}>
        <DialogTitle>New valuation</DialogTitle>
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
                value={form.valuation_date}
                onChange={(e) => update("valuation_date", e.target.value)}
                InputLabelProps={{ shrink: true }}
                required
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Source"
                select
                value={form.source}
                onChange={(e) => update("source", e.target.value)}
                fullWidth
              >
                <MenuItem value="">—</MenuItem>
                {VALUATION_SOURCES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Post-money (₹Cr)"
                type="number"
                value={form.post_money_valuation_cr}
                onChange={(e) => update("post_money_valuation_cr", e.target.value)}
                inputProps={{ step: "0.0001", min: "0" }}
                required
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Pre-money (₹Cr)"
                type="number"
                value={form.pre_money_valuation_cr}
                onChange={(e) => update("pre_money_valuation_cr", e.target.value)}
                inputProps={{ step: "0.0001", min: "0" }}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Currency"
                value={form.currency}
                onChange={(e) => update("currency", e.target.value.toUpperCase())}
                inputProps={{ maxLength: 10 }}
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
          <Button onClick={onClose} disabled={create.isPending}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Add valuation"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
