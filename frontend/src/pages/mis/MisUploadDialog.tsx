import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Button from "@mui/material/Button";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid";
import MenuItem from "@mui/material/MenuItem";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

import { useCompanies } from "../../api/companies";
import {
  useCreateMisSubmission,
  useUploadMisFile,
} from "../../api/mis";

interface MisUploadDialogProps {
  open: boolean;
  onClose: () => void;
}

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function deriveFiscalYear(year: number, month: number): string {
  const fyEnd = year + (month >= 4 ? 1 : 0);
  return `FY${String(fyEnd).slice(-2)}`;
}

export default function MisUploadDialog({ open, onClose }: MisUploadDialogProps) {
  const navigate = useNavigate();
  const today = new Date();
  const [companyCode, setCompanyCode] = useState("");
  const [periodYear, setPeriodYear] = useState(today.getFullYear());
  const [periodMonth, setPeriodMonth] = useState(today.getMonth() + 1);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const create = useCreateMisSubmission();
  const upload = useUploadMisFile();
  const companies = useCompanies({ limit: 1000 });

  useEffect(() => {
    if (open) {
      setCompanyCode("");
      setFile(null);
      setError(null);
      setPeriodYear(today.getFullYear());
      setPeriodMonth(today.getMonth() + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const companyOptions =
    companies.data?.items.map((c) => ({
      // The MIS schema uses string company_id (e.g. "company_01"). We derive
      // it from the portfolio company's display name for the demo: lowercase
      // and replace spaces with underscores. The analyst can also type a
      // freeform code if their internal convention differs.
      code:
        c.display_name?.toLowerCase().replace(/\s+/g, "_") ??
        c.company_name.toLowerCase().replace(/\s+/g, "_"),
      label: c.display_name || c.company_name,
    })) ?? [];

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!companyCode) {
      setError("Pick a company.");
      return;
    }
    if (!file) {
      setError("Attach an .xlsx file.");
      return;
    }
    try {
      const sub = await create.mutateAsync({
        company_id: companyCode,
        period_year: periodYear,
        period_month: periodMonth,
        fiscal_year: deriveFiscalYear(periodYear, periodMonth),
      });
      await upload.mutateAsync({ id: sub.id, file });
      onClose();
      navigate(`/mis/${sub.id}`);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Upload failed");
    }
  }

  const submitting = create.isPending || upload.isPending;

  return (
    <Dialog open={open} onClose={onClose} fullWidth maxWidth="sm">
      <form onSubmit={handleSubmit}>
        <DialogTitle>New MIS submission</DialogTitle>
        <DialogContent dividers>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}
          <Grid container spacing={2}>
            <Grid item xs={12}>
              <Autocomplete
                freeSolo
                options={companyOptions}
                getOptionLabel={(opt) =>
                  typeof opt === "string" ? opt : `${opt.label} (${opt.code})`
                }
                onInputChange={(_, value) => setCompanyCode(value)}
                renderInput={(params) => (
                  <TextField
                    {...params}
                    label="Company code"
                    helperText="Internal code (e.g. company_01). Pick from the list or type."
                    required
                    fullWidth
                  />
                )}
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                label="Year"
                type="number"
                value={periodYear}
                onChange={(e) => setPeriodYear(Number(e.target.value) || 0)}
                inputProps={{ min: 2000, max: 2100 }}
                required
                fullWidth
              />
            </Grid>
            <Grid item xs={6}>
              <TextField
                label="Month"
                select
                value={periodMonth}
                onChange={(e) => setPeriodMonth(Number(e.target.value))}
                required
                fullWidth
              >
                {MONTHS.map((m, i) => (
                  <MenuItem key={m} value={i + 1}>
                    {m}
                  </MenuItem>
                ))}
              </TextField>
            </Grid>
            <Grid item xs={12}>
              <Button variant="outlined" component="label" fullWidth>
                {file ? `Selected: ${file.name}` : "Choose .xlsx file"}
                <input
                  hidden
                  type="file"
                  accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  onChange={onFileChange}
                />
              </Button>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                Only .xlsx files. Templates supported in Sprint 5: Company_01-style consolidated MIS,
                Company_02-style monthly report.
              </Typography>
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={submitting}>
            {submitting ? "Uploading…" : "Create + upload"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
