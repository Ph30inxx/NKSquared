import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import LinearProgress from "@mui/material/LinearProgress";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import CalendarTodayIcon from "@mui/icons-material/CalendarToday";
import BusinessIcon from "@mui/icons-material/Business";
import TimerIcon from "@mui/icons-material/Timer";

interface TokenPayload {
  company_id: number;
  company_name: string;
  company_code: string | null;
  period_year: number;
  period_month: number;
  expires_in_days: number;
}

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

export default function PublicUploadPage() {
  const { token = "" } = useParams<{ token: string }>();

  const publicApi = useMemo(
    () =>
      axios.create({
        baseURL: "/api/v1",
        headers: { "Content-Type": "application/json" },
      }),
    [],
  );

  const [payload, setPayload] = useState<TokenPayload | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setVerifying(true);
    setVerifyError(null);
    publicApi
      .get<TokenPayload>("/public/upload/verify", { params: { token } })
      .then((res) => {
        if (!cancelled) setPayload(res.data);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = err?.response?.data?.detail ?? "This link is invalid or has expired.";
        setVerifyError(detail);
      })
      .finally(() => {
        if (!cancelled) setVerifying(false);
      });
    return () => {
      cancelled = true;
    };
  }, [token, publicApi]);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setSubmitError("Please select an .xlsx file to upload.");
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      await publicApi.post("/public/upload", form, {
        params: { token },
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDone(true);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Upload failed. Please try again.";
      setSubmitError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #EEF2FF 0%, #F4F6FA 50%, #E8F0FE 100%)",
        p: 2,
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 480 }}>
        {/* Brand */}
        <Stack alignItems="center" spacing={1} sx={{ mb: 3 }}>
          <Box
            sx={{
              width: 44,
              height: 44,
              borderRadius: 2.5,
              background: "linear-gradient(135deg, #4F75E8 0%, #1B4FD8 60%, #1340B0 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 6px 20px rgba(27, 79, 216, 0.30)",
            }}
          >
            <Typography sx={{ color: "#fff", fontWeight: 800, fontSize: "0.9rem" }}>NK</Typography>
          </Box>
          <Typography variant="h6" fontWeight={700} letterSpacing="-0.02em">
            NKSquared
          </Typography>
        </Stack>

        <Paper
          sx={{
            overflow: "hidden",
            boxShadow: "0 20px 60px rgba(0,0,0,0.10), 0 4px 16px rgba(0,0,0,0.06)",
            border: "none",
          }}
        >
          {/* Header bar */}
          <Box sx={{ px: 3, py: 2.5, bgcolor: "primary.main" }}>
            <Typography variant="h6" sx={{ color: "#fff", fontWeight: 700 }}>
              MIS File Upload
            </Typography>
            <Typography variant="body2" sx={{ color: "rgba(255,255,255,0.75)", mt: 0.25 }}>
              Submit your monthly information report
            </Typography>
          </Box>

          <Box sx={{ p: 3 }}>
            {/* Loading */}
            {verifying && (
              <Stack spacing={2} alignItems="center" py={4}>
                <CircularProgress size={32} />
                <Typography color="text.secondary" variant="body2">
                  Validating your upload link…
                </Typography>
              </Stack>
            )}

            {/* Error */}
            {!verifying && verifyError && (
              <Stack spacing={2} py={2}>
                <Alert severity="error" variant="filled">
                  {verifyError}
                </Alert>
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  Please contact your fund manager to request a new link.
                </Typography>
              </Stack>
            )}

            {/* Upload form */}
            {!verifying && !verifyError && payload && !done && (
              <Box component="form" onSubmit={handleSubmit}>
                {/* Submission details */}
                <Stack spacing={1.5} sx={{ mb: 3 }}>
                  <Stack direction="row" spacing={1} alignItems="center">
                    <BusinessIcon sx={{ fontSize: 18, color: "text.secondary" }} />
                    <Typography variant="body2" color="text.secondary">Company</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ ml: "auto !important" }}>
                      {payload.company_name}
                    </Typography>
                  </Stack>
                  <Divider />
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CalendarTodayIcon sx={{ fontSize: 18, color: "text.secondary" }} />
                    <Typography variant="body2" color="text.secondary">Period</Typography>
                    <Typography variant="body2" fontWeight={600} sx={{ ml: "auto !important" }}>
                      {MONTHS[payload.period_month - 1]} {payload.period_year}
                    </Typography>
                  </Stack>
                  <Divider />
                  <Stack direction="row" spacing={1} alignItems="center">
                    <TimerIcon sx={{ fontSize: 18, color: payload.expires_in_days <= 3 ? "error.main" : "text.secondary" }} />
                    <Typography variant="body2" color="text.secondary">Link expires</Typography>
                    <Chip
                      label={`${payload.expires_in_days} day${payload.expires_in_days !== 1 ? "s" : ""} remaining`}
                      size="small"
                      color={payload.expires_in_days <= 3 ? "error" : payload.expires_in_days <= 7 ? "warning" : "success"}
                      sx={{ ml: "auto !important" }}
                    />
                  </Stack>
                </Stack>

                {/* File picker */}
                <Button
                  variant={file ? "contained" : "outlined"}
                  component="label"
                  fullWidth
                  startIcon={<UploadFileIcon />}
                  color={file ? "primary" : "inherit"}
                  sx={{ mb: 2, py: 1.5, justifyContent: "flex-start" }}
                >
                  {file ? file.name : "Choose .xlsx file…"}
                  <input
                    type="file"
                    hidden
                    accept=".xlsx"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                  />
                </Button>

                {submitError && (
                  <Alert severity="error" sx={{ mb: 2 }}>
                    {submitError}
                  </Alert>
                )}

                {submitting && <LinearProgress sx={{ mb: 2, borderRadius: 1 }} />}

                <Button
                  type="submit"
                  variant="contained"
                  fullWidth
                  size="large"
                  disabled={submitting || !file}
                  sx={{ py: 1.25 }}
                >
                  {submitting ? "Uploading…" : "Submit"}
                </Button>

                <Typography variant="caption" color="text.disabled" display="block" textAlign="center" mt={2}>
                  Only .xlsx files are accepted. Max file size: 10 MB.
                </Typography>
              </Box>
            )}

            {/* Success */}
            {done && (
              <Stack alignItems="center" spacing={2} py={4}>
                <CheckCircleIcon sx={{ fontSize: 64, color: "success.main" }} />
                <Box textAlign="center">
                  <Typography variant="h6" fontWeight={700}>
                    File received!
                  </Typography>
                  <Typography variant="body2" color="text.secondary" mt={0.5}>
                    Thank you. Our team will review your submission and confirm receipt. You can safely close this window.
                  </Typography>
                </Box>
              </Stack>
            )}
          </Box>
        </Paper>

        <Typography variant="caption" color="text.disabled" textAlign="center" display="block" sx={{ mt: 3 }}>
          © {new Date().getFullYear()} NKSquared. Secure file transfer.
        </Typography>
      </Box>
    </Box>
  );
}
