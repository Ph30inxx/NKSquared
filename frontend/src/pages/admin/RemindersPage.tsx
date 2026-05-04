import { useMemo, useState, type FormEvent } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import Alert from "@mui/material/Alert";
import Autocomplete from "@mui/material/Autocomplete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import MenuItem from "@mui/material/MenuItem";
import Pagination from "@mui/material/Pagination";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Switch from "@mui/material/Switch";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

import { useCompanies } from "../../api/companies";
import {
  REMINDER_TYPES,
  type ReminderType,
  useCreateReminderSchedule,
  useDeleteReminderSchedule,
  useReminderLogs,
  useReminderSchedules,
  useUpdateReminderSchedule,
} from "../../api/reminders";

const PAGE_SIZE = 25;

export default function RemindersPage() {
  const [tab, setTab] = useState<"schedules" | "logs">("schedules");

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Reminders
      </Typography>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ mb: 2 }}>
        <Tab label="Schedules" value="schedules" />
        <Tab label="Logs" value="logs" />
      </Tabs>
      {tab === "schedules" ? <SchedulesTab /> : <LogsTab />}
    </Box>
  );
}

// ─── Schedules tab ────────────────────────────────────────────────────────────

function SchedulesTab() {
  const schedules = useReminderSchedules();
  const companies = useCompanies({ limit: 1000 });
  const update = useUpdateReminderSchedule();
  const remove = useDeleteReminderSchedule();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const companyMap = useMemo(() => {
    const map = new Map<number, string>();
    (companies.data?.items ?? []).forEach((c) => {
      map.set(c.id, c.display_name || c.company_name);
    });
    return map;
  }, [companies.data]);

  if (schedules.isLoading || companies.isLoading) {
    return <CircularProgress />;
  }
  if (schedules.error) {
    return <Alert severity="error">Failed to load schedules.</Alert>;
  }

  return (
    <Box>
      <Stack direction="row" justifyContent="flex-end" mb={2}>
        <Button startIcon={<AddIcon />} variant="contained" onClick={() => setDialogOpen(true)}>
          New schedule
        </Button>
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Company</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="center">Enabled</TableCell>
              <TableCell align="right">Cadence (days)</TableCell>
              <TableCell align="right">First reminder offset</TableCell>
              <TableCell align="right">Escalation threshold</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {(schedules.data ?? []).map((s) => (
              <TableRow key={s.id} hover>
                <TableCell>{companyMap.get(s.company_id) ?? `#${s.company_id}`}</TableCell>
                <TableCell>{s.reminder_type}</TableCell>
                <TableCell align="center">
                  <Switch
                    size="small"
                    checked={s.enabled}
                    onChange={(e) =>
                      update.mutate(
                        { id: s.id, payload: { enabled: e.target.checked } },
                        { onError: (err: any) => setError(err?.response?.data?.detail ?? "Update failed") },
                      )
                    }
                  />
                </TableCell>
                <TableCell align="right">
                  <NumberCell
                    value={s.cadence_days}
                    onCommit={(v) =>
                      update.mutate(
                        { id: s.id, payload: { cadence_days: v } },
                        { onError: (err: any) => setError(err?.response?.data?.detail ?? "Update failed") },
                      )
                    }
                  />
                </TableCell>
                <TableCell align="right">
                  <NumberCell
                    value={s.first_reminder_offset_days}
                    onCommit={(v) =>
                      update.mutate(
                        { id: s.id, payload: { first_reminder_offset_days: v } },
                        { onError: (err: any) => setError(err?.response?.data?.detail ?? "Update failed") },
                      )
                    }
                  />
                </TableCell>
                <TableCell align="right">
                  <NumberCell
                    value={s.escalation_threshold}
                    onCommit={(v) =>
                      update.mutate(
                        { id: s.id, payload: { escalation_threshold: v } },
                        { onError: (err: any) => setError(err?.response?.data?.detail ?? "Update failed") },
                      )
                    }
                  />
                </TableCell>
                <TableCell align="right">
                  <IconButton
                    size="small"
                    onClick={() => {
                      if (window.confirm("Delete this schedule?")) {
                        remove.mutate(s.id, {
                          onError: (err: any) =>
                            setError(err?.response?.data?.detail ?? "Delete failed"),
                        });
                      }
                    }}
                  >
                    <DeleteIcon fontSize="small" />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
            {(schedules.data ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4, color: "text.secondary" }}>
                  No reminder schedules configured yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <NewScheduleDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        companies={companies.data?.items ?? []}
      />
    </Box>
  );
}

function NumberCell({
  value,
  onCommit,
}: {
  value: number;
  onCommit: (v: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  return (
    <TextField
      size="small"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        const n = Number(draft);
        if (Number.isFinite(n) && n !== value) {
          onCommit(n);
        } else if (!Number.isFinite(n)) {
          setDraft(String(value));
        }
      }}
      inputProps={{ inputMode: "numeric", style: { textAlign: "right", width: 60 } }}
    />
  );
}

function NewScheduleDialog({
  open,
  onClose,
  companies,
}: {
  open: boolean;
  onClose: () => void;
  companies: { id: number; company_name: string; display_name: string | null }[];
}) {
  const create = useCreateReminderSchedule();
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [reminderType, setReminderType] = useState<ReminderType>("MIS_MONTHLY");
  const [cadence, setCadence] = useState(7);
  const [offset, setOffset] = useState(5);
  const [threshold, setThreshold] = useState(3);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setCompanyId(null);
    setReminderType("MIS_MONTHLY");
    setCadence(7);
    setOffset(5);
    setThreshold(3);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (companyId == null) {
      setError("Pick a company.");
      return;
    }
    try {
      await create.mutateAsync({
        company_id: companyId,
        reminder_type: reminderType,
        enabled: true,
        cadence_days: cadence,
        first_reminder_offset_days: offset,
        escalation_threshold: threshold,
      });
      reset();
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Could not create schedule.");
    }
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>New reminder schedule</DialogTitle>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogContent>
          <Stack spacing={2}>
            <Autocomplete
              options={companies}
              getOptionLabel={(c) => c.display_name || c.company_name}
              value={companies.find((c) => c.id === companyId) ?? null}
              onChange={(_, v) => setCompanyId(v?.id ?? null)}
              renderInput={(params) => <TextField {...params} label="Company" required />}
            />
            <TextField
              select
              label="Type"
              value={reminderType}
              onChange={(e) => setReminderType(e.target.value as ReminderType)}
            >
              {REMINDER_TYPES.map((t) => (
                <MenuItem key={t} value={t}>
                  {t}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="Cadence (days)"
              type="number"
              value={cadence}
              onChange={(e) => setCadence(Number(e.target.value))}
            />
            <TextField
              label="First reminder offset (days)"
              type="number"
              value={offset}
              onChange={(e) => setOffset(Number(e.target.value))}
            />
            <TextField
              label="Escalation threshold"
              type="number"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
            />
            {error && <Alert severity="error">{error}</Alert>}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}

// ─── Logs tab ────────────────────────────────────────────────────────────────

function LogsTab() {
  const [page, setPage] = useState(1);
  const offset = (page - 1) * PAGE_SIZE;
  const logs = useReminderLogs({ limit: PAGE_SIZE, offset });
  const companies = useCompanies({ limit: 1000 });

  const companyMap = useMemo(() => {
    const map = new Map<number, string>();
    (companies.data?.items ?? []).forEach((c) => {
      map.set(c.id, c.display_name || c.company_name);
    });
    return map;
  }, [companies.data]);

  if (logs.isLoading) return <CircularProgress />;
  if (logs.error) return <Alert severity="error">Failed to load logs.</Alert>;

  const total = logs.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <Box>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Sent at</TableCell>
              <TableCell>Company</TableCell>
              <TableCell>Period</TableCell>
              <TableCell>Recipient</TableCell>
              <TableCell>Subject</TableCell>
              <TableCell align="center">Status</TableCell>
              <TableCell align="center">Escalation</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {(logs.data?.items ?? []).map((log) => (
              <TableRow key={log.id} hover>
                <TableCell>{new Date(log.sent_at).toLocaleString()}</TableCell>
                <TableCell>{companyMap.get(log.company_id) ?? `#${log.company_id}`}</TableCell>
                <TableCell>{log.related_period ?? "—"}</TableCell>
                <TableCell>{log.recipient_email ?? "—"}</TableCell>
                <TableCell>{log.subject ?? "—"}</TableCell>
                <TableCell align="center">
                  <Chip
                    label={log.status}
                    size="small"
                    color={log.status === "Sent" ? "success" : log.status === "Failed" ? "error" : "default"}
                  />
                </TableCell>
                <TableCell align="center">
                  {log.is_escalation ? <Chip label="ESC" size="small" color="warning" /> : ""}
                </TableCell>
              </TableRow>
            ))}
            {(logs.data?.items ?? []).length === 0 && (
              <TableRow>
                <TableCell colSpan={7} align="center" sx={{ py: 4, color: "text.secondary" }}>
                  No reminders have been sent yet.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {pageCount > 1 && (
        <Stack alignItems="center" mt={2}>
          <Pagination count={pageCount} page={page} onChange={(_, p) => setPage(p)} />
        </Stack>
      )}
    </Box>
  );
}
