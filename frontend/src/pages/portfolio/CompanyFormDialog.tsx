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
  ASSET_CLASSES,
  CompanyDetail,
  CompanyWritePayload,
  INVESTMENT_STATUSES,
  PORTFOLIO_STATUSES,
  PORTFOLIO_TYPES,
  useCreateCompany,
  useUpdateCompany,
} from "../../api/companies";

interface CompanyFormDialogProps {
  open: boolean;
  onClose: () => void;
  initial?: CompanyDetail | null;
  onCreated?: (company: CompanyDetail) => void;
  onUpdated?: (company: CompanyDetail) => void;
}

const EMPTY: CompanyWritePayload = {
  company_name: "",
  display_name: "",
  portfolio_type: "",
  investment_status: null,
  portfolio_status: null,
  asset_class: null,
  sector: "",
  sub_sector: "",
  country: "",
  date_of_first_investment: "",
  current_value_cr: "",
  currency: "INR",
  reporting_frequency: "Monthly",
  notes: "",
};

function detailToPayload(c: CompanyDetail): CompanyWritePayload {
  return {
    company_name: c.company_name,
    display_name: c.display_name ?? "",
    portfolio_type: c.portfolio_type ?? "",
    investment_status: (c.investment_status as CompanyWritePayload["investment_status"]) ?? null,
    portfolio_status: (c.portfolio_status as CompanyWritePayload["portfolio_status"]) ?? null,
    asset_class: (c.asset_class as CompanyWritePayload["asset_class"]) ?? null,
    sector: c.sector ?? "",
    sub_sector: c.sub_sector ?? "",
    country: c.country ?? "",
    date_of_first_investment: c.date_of_first_investment ?? "",
    current_value_cr: c.current_value_cr ?? "",
    currency: c.currency,
    reporting_frequency: c.reporting_frequency,
    notes: c.notes ?? "",
  };
}

function nullify(payload: CompanyWritePayload): CompanyWritePayload {
  // Convert empty strings to null so the backend stores NULL rather than ''.
  const out: Record<string, unknown> = { ...payload };
  for (const [k, v] of Object.entries(out)) {
    if (v === "") out[k] = null;
  }
  return out as unknown as CompanyWritePayload;
}

export default function CompanyFormDialog({
  open,
  onClose,
  initial,
  onCreated,
  onUpdated,
}: CompanyFormDialogProps) {
  const isEdit = Boolean(initial);
  const [form, setForm] = useState<CompanyWritePayload>(EMPTY);
  const [error, setError] = useState<string | null>(null);

  const createMut = useCreateCompany();
  const updateMut = useUpdateCompany(initial?.id ?? 0);

  useEffect(() => {
    setForm(initial ? detailToPayload(initial) : EMPTY);
    setError(null);
  }, [initial, open]);

  function update<K extends keyof CompanyWritePayload>(key: K, value: CompanyWritePayload[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const payload = nullify(form);
      if (isEdit && initial) {
        const updated = await updateMut.mutateAsync(payload);
        onUpdated?.(updated);
      } else {
        const created = await createMut.mutateAsync(payload);
        onCreated?.(created);
      }
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setError(typeof detail === "string" ? detail : "Save failed");
    }
  }

  const submitting = createMut.isPending || updateMut.isPending;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="md">
      <form onSubmit={handleSubmit}>
        <DialogTitle>{isEdit ? "Edit company" : "New company"}</DialogTitle>
        <DialogContent dividers>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Company name"
                value={form.company_name}
                onChange={(e) => update("company_name", e.target.value)}
                required
                fullWidth
                autoFocus
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Display name"
                value={form.display_name ?? ""}
                onChange={(e) => update("display_name", e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Vehicle"
                select
                value={form.portfolio_type ?? ""}
                onChange={(e) => update("portfolio_type", e.target.value)}
                fullWidth
              >
                <MenuItem value="">—</MenuItem>
                {PORTFOLIO_TYPES.map((t) => (
                  <MenuItem key={t} value={t}>
                    {t.replace(/_/g, " ")}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Asset class"
                select
                value={form.asset_class ?? ""}
                onChange={(e) =>
                  update("asset_class", (e.target.value || null) as CompanyWritePayload["asset_class"])
                }
                fullWidth
              >
                <MenuItem value="">—</MenuItem>
                {ASSET_CLASSES.map((a) => (
                  <MenuItem key={a} value={a}>
                    {a.replace(/_/g, " ")}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Investment status"
                select
                value={form.investment_status ?? ""}
                onChange={(e) =>
                  update(
                    "investment_status",
                    (e.target.value || null) as CompanyWritePayload["investment_status"],
                  )
                }
                fullWidth
              >
                <MenuItem value="">—</MenuItem>
                {INVESTMENT_STATUSES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {s.replace(/_/g, " ")}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Portfolio status"
                select
                value={form.portfolio_status ?? ""}
                onChange={(e) =>
                  update(
                    "portfolio_status",
                    (e.target.value || null) as CompanyWritePayload["portfolio_status"],
                  )
                }
                fullWidth
              >
                <MenuItem value="">—</MenuItem>
                {PORTFOLIO_STATUSES.map((s) => (
                  <MenuItem key={s} value={s}>
                    {s}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Sector"
                value={form.sector ?? ""}
                onChange={(e) => update("sector", e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Sub-sector"
                value={form.sub_sector ?? ""}
                onChange={(e) => update("sub_sector", e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Country"
                value={form.country ?? ""}
                onChange={(e) => update("country", e.target.value)}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Date of first investment"
                type="date"
                value={form.date_of_first_investment ?? ""}
                onChange={(e) => update("date_of_first_investment", e.target.value)}
                InputLabelProps={{ shrink: true }}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Currency"
                value={form.currency ?? "INR"}
                onChange={(e) => update("currency", e.target.value.toUpperCase())}
                inputProps={{ maxLength: 10 }}
                fullWidth
              />
            </Grid>
            <Grid item xs={12} sm={6}>
              <TextField
                label="Current value (₹Cr)"
                type="number"
                value={form.current_value_cr ?? ""}
                onChange={(e) => update("current_value_cr", e.target.value)}
                fullWidth
                inputProps={{ step: "0.0001" }}
              />
            </Grid>
            <Grid item xs={12}>
              <TextField
                label="Notes"
                value={form.notes ?? ""}
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
            {submitting ? "Saving…" : isEdit ? "Save changes" : "Create company"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
