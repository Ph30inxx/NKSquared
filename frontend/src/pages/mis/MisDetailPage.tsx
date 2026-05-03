import { useState, type ChangeEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import RefreshIcon from "@mui/icons-material/Refresh";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
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
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";

import {
  MisSubmissionStatus,
  useApproveMisSubmission,
  useMisSubmission,
  usePreviewMisSubmission,
  useRejectMisSubmission,
  useUploadMisFile,
} from "../../api/mis";
import { formatCr, formatDate } from "../../utils/format";

const STATUS_COLOR: Record<
  MisSubmissionStatus,
  "default" | "warning" | "info" | "success" | "error"
> = {
  Pending: "default",
  Submitted: "info",
  "Under Review": "warning",
  Approved: "success",
  Rejected: "error",
  "Resubmission Required": "warning",
};

interface ToastState {
  severity: "success" | "error" | "info";
  message: string;
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

function periodLabel(year: number, month: number): string {
  const d = new Date(year, month - 1, 1);
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "long" });
}

export default function MisDetailPage() {
  const params = useParams();
  const navigate = useNavigate();
  const id = params.id ? Number(params.id) : null;

  const submission = useMisSubmission(id);
  const upload = useUploadMisFile();
  const preview = usePreviewMisSubmission(id);
  const approve = useApproveMisSubmission();
  const reject = useRejectMisSubmission();

  const [toast, setToast] = useState<ToastState | null>(null);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  if (id == null) return <Alert severity="error">Missing submission id.</Alert>;
  if (submission.isLoading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }
  if (submission.isError || !submission.data) {
    return <Alert severity="error">Could not load submission.</Alert>;
  }

  const s = submission.data;
  const canUpload = s.status === "Pending";
  const canReview = s.status === "Submitted" || s.status === "Under Review";

  async function handleFileChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await upload.mutateAsync({ id: s.id, file });
      setToast({ severity: "success", message: "File uploaded" });
    } catch (err) {
      setToast({ severity: "error", message: extractDetail(err) });
    }
  }

  async function handleRefreshPreview() {
    try {
      await preview.refetch({ throwOnError: true });
    } catch (err) {
      setToast({ severity: "error", message: extractDetail(err) });
    }
  }

  async function handleApprove() {
    try {
      await approve.mutateAsync(s.id);
      setToast({ severity: "success", message: "Submission approved" });
    } catch (err) {
      setToast({ severity: "error", message: extractDetail(err) });
    }
  }

  async function handleReject() {
    if (!rejectReason.trim()) {
      setToast({ severity: "error", message: "Reason is required" });
      return;
    }
    try {
      await reject.mutateAsync({ id: s.id, reason: rejectReason.trim() });
      setRejectOpen(false);
      setRejectReason("");
      setToast({ severity: "success", message: "Submission rejected" });
    } catch (err) {
      setToast({ severity: "error", message: extractDetail(err) });
    }
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" spacing={1} alignItems="center">
        <IconButton onClick={() => navigate("/mis")} size="small">
          <ArrowBackIcon />
        </IconButton>
        <Typography variant="h4" component="h1">
          Submission #{s.id}
        </Typography>
        <Chip
          label={s.status}
          color={STATUS_COLOR[s.status as MisSubmissionStatus] ?? "default"}
          size="small"
        />
        <Box flexGrow={1} />
        {canUpload && (
          <Button
            variant="contained"
            component="label"
            startIcon={<UploadFileIcon />}
            disabled={upload.isPending}
          >
            {upload.isPending ? "Uploading…" : "Upload file"}
            <input
              hidden
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={handleFileChange}
            />
          </Button>
        )}
        {canReview && (
          <>
            <Button
              variant="contained"
              color="success"
              startIcon={<CheckIcon />}
              onClick={handleApprove}
              disabled={approve.isPending}
            >
              {approve.isPending ? "Approving…" : "Approve"}
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<CloseIcon />}
              onClick={() => setRejectOpen(true)}
            >
              Reject
            </Button>
          </>
        )}
      </Stack>

      {s.rejection_reason && (
        <Alert severity="error">Rejection reason: {s.rejection_reason}</Alert>
      )}

      <Paper sx={{ p: 3 }}>
        <Grid container spacing={3}>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Company" value={s.company_id} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Period" value={periodLabel(s.period_year, s.period_month)} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Fiscal year" value={s.fiscal_year} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Source file" value={s.source_file_name} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Uploaded at" value={s.uploaded_at ? formatDate(s.uploaded_at) : null} />
          </Grid>
          <Grid item xs={6} sm={3}>
            <MetadataRow label="Reviewed at" value={s.reviewed_at ? formatDate(s.reviewed_at) : null} />
          </Grid>
          <Grid item xs={12} sm={6}>
            <MetadataRow label="Notes" value={s.notes} />
          </Grid>
        </Grid>
      </Paper>

      <Paper sx={{ p: 3 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">Preview</Typography>
          <Button
            startIcon={<RefreshIcon />}
            onClick={handleRefreshPreview}
            disabled={!s.source_file_name || preview.isFetching}
            size="small"
          >
            {preview.isFetching ? "Parsing…" : "Refresh preview"}
          </Button>
        </Stack>

        {!s.source_file_name && (
          <Typography variant="body2" color="text.secondary">
            Upload a file to enable preview.
          </Typography>
        )}

        {preview.isError && (
          <Alert severity="error">{extractDetail(preview.error)}</Alert>
        )}

        {preview.data && (
          <>
            <Stack direction="row" spacing={2} mb={2}>
              <Chip label={`Template: ${preview.data.template}`} />
              <Chip label={`${preview.data.monthly_count} monthly rows`} variant="outlined" />
              <Chip label={`${preview.data.bu_count} BU rows`} variant="outlined" />
              {preview.data.outlet_count > 0 && (
                <Chip label={`${preview.data.outlet_count} outlet rows`} variant="outlined" />
              )}
            </Stack>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Month</TableCell>
                    <TableCell>Geography</TableCell>
                    <TableCell align="right">Revenue (Lacs)</TableCell>
                    <TableCell align="right">COGS</TableCell>
                    <TableCell align="right">Gross margin</TableCell>
                    <TableCell align="right">EBITDA</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.data.sample_monthly.map((r, i) => (
                    <TableRow key={i}>
                      <TableCell>{formatDate(r.month_date)}</TableCell>
                      <TableCell>{r.geography}</TableCell>
                      <TableCell align="right">{formatCr(r.revenue_lacs)}</TableCell>
                      <TableCell align="right">{formatCr(r.cogs_lacs)}</TableCell>
                      <TableCell align="right">{formatCr(r.gross_margin_lacs)}</TableCell>
                      <TableCell align="right">{formatCr(r.ebitda_lacs)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </Paper>

      <Dialog open={rejectOpen} onClose={() => setRejectOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>Reject submission</DialogTitle>
        <DialogContent>
          <TextField
            label="Reason"
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            multiline
            minRows={3}
            fullWidth
            autoFocus
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRejectOpen(false)}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleReject} disabled={reject.isPending}>
            {reject.isPending ? "Rejecting…" : "Confirm reject"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={toast != null}
        autoHideDuration={toast?.severity === "error" ? 6000 : 2500}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        {toast ? (
          <Alert
            severity={toast.severity}
            variant="filled"
            onClose={() => setToast(null)}
            sx={{ width: "100%" }}
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Stack>
  );
}

function extractDetail(err: unknown): string {
  const detail =
    (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const first = detail[0] as { msg?: string } | undefined;
    if (first?.msg) return first.msg;
  }
  return (err as { message?: string })?.message ?? "Request failed";
}
