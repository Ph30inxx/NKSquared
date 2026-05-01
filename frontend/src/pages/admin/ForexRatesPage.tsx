import { useState, type FormEvent } from "react";
import AddIcon from "@mui/icons-material/Add";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

import { useForexRates, useUpsertForexRate } from "../../api/forex";
import { formatDate } from "../../utils/format";

interface NewRateState {
  from_currency: string;
  to_currency: string;
  rate: string;
  effective_date: string;
  source: string;
}

const EMPTY: NewRateState = {
  from_currency: "",
  to_currency: "INR",
  rate: "",
  effective_date: new Date().toISOString().slice(0, 10),
  source: "manual",
};

export default function ForexRatesPage() {
  const [filterFrom, setFilterFrom] = useState("");
  const [filterTo, setFilterTo] = useState("");
  const rates = useForexRates({
    from: filterFrom || undefined,
    to: filterTo || undefined,
    limit: 200,
  });

  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<NewRateState>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const upsert = useUpsertForexRate();

  function update<K extends keyof NewRateState>(key: K, value: NewRateState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.from_currency || !form.rate || !form.effective_date) {
      setError("From currency, rate, and date are required.");
      return;
    }
    try {
      await upsert.mutateAsync({
        from_currency: form.from_currency.toUpperCase(),
        to_currency: form.to_currency.toUpperCase(),
        rate: form.rate,
        effective_date: form.effective_date,
        source: form.source || null,
      });
      setDialogOpen(false);
      setForm(EMPTY);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail;
      setError(typeof detail === "string" ? detail : "Save failed");
    }
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" component="h1">
          FX rates
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setForm(EMPTY);
            setError(null);
            setDialogOpen(true);
          }}
        >
          Add rate
        </Button>
      </Stack>

      <Paper sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            label="From currency"
            size="small"
            value={filterFrom}
            onChange={(e) => setFilterFrom(e.target.value.toUpperCase())}
            inputProps={{ maxLength: 10 }}
            sx={{ minWidth: 160 }}
          />
          <TextField
            label="To currency"
            size="small"
            value={filterTo}
            onChange={(e) => setFilterTo(e.target.value.toUpperCase())}
            inputProps={{ maxLength: 10 }}
            sx={{ minWidth: 160 }}
          />
        </Stack>
      </Paper>

      <Paper>
        {rates.isLoading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Effective date</TableCell>
                  <TableCell>From</TableCell>
                  <TableCell>To</TableCell>
                  <TableCell align="right">Rate</TableCell>
                  <TableCell>Source</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rates.data?.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell>{formatDate(r.effective_date)}</TableCell>
                    <TableCell>{r.from_currency}</TableCell>
                    <TableCell>{r.to_currency}</TableCell>
                    <TableCell align="right">{Number(r.rate).toFixed(4)}</TableCell>
                    <TableCell>{r.source ?? "—"}</TableCell>
                  </TableRow>
                ))}
                {rates.data && rates.data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Box py={3} textAlign="center" color="text.secondary">
                        No rates match your filters.
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="xs">
        <form onSubmit={handleSubmit}>
          <DialogTitle>Add FX rate</DialogTitle>
          <DialogContent dividers>
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <TextField
                  label="From currency"
                  value={form.from_currency}
                  onChange={(e) => update("from_currency", e.target.value.toUpperCase())}
                  inputProps={{ maxLength: 10 }}
                  required
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="To currency"
                  value={form.to_currency}
                  onChange={(e) => update("to_currency", e.target.value.toUpperCase())}
                  inputProps={{ maxLength: 10 }}
                  required
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Rate"
                  type="number"
                  value={form.rate}
                  onChange={(e) => update("rate", e.target.value)}
                  inputProps={{ step: "0.000001", min: "0" }}
                  required
                  fullWidth
                />
              </Grid>
              <Grid item xs={6}>
                <TextField
                  label="Effective date"
                  type="date"
                  value={form.effective_date}
                  onChange={(e) => update("effective_date", e.target.value)}
                  InputLabelProps={{ shrink: true }}
                  required
                  fullWidth
                />
              </Grid>
              <Grid item xs={12}>
                <TextField
                  label="Source"
                  value={form.source}
                  onChange={(e) => update("source", e.target.value)}
                  fullWidth
                />
              </Grid>
            </Grid>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setDialogOpen(false)} disabled={upsert.isPending}>
              Cancel
            </Button>
            <Button type="submit" variant="contained" disabled={upsert.isPending}>
              {upsert.isPending ? "Saving…" : "Save"}
            </Button>
          </DialogActions>
        </form>
      </Dialog>
    </Stack>
  );
}
