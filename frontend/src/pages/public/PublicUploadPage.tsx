import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";

interface TokenPayload {
  company_id: number;
  company_name: string;
  company_code: string | null;
  period_year: number;
  period_month: number;
  expires_in_days: number;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
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
      setSubmitError("Pick an .xlsx file to upload.");
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
    } catch (err: any) {
      const detail = err?.response?.data?.detail ?? "Upload failed. Please try again.";
      setSubmitError(detail);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Container maxWidth="sm" sx={{ py: 6 }}>
      <Paper elevation={1} sx={{ p: 4 }}>
        <Typography variant="h5" gutterBottom>
          MIS upload
        </Typography>

        {verifying && (
          <Box display="flex" alignItems="center" gap={2} py={4}>
            <CircularProgress size={24} />
            <Typography>Validating link…</Typography>
          </Box>
        )}

        {!verifying && verifyError && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {verifyError}
          </Alert>
        )}

        {!verifying && !verifyError && payload && !done && (
          <Box component="form" onSubmit={handleSubmit} mt={1}>
            <Stack spacing={1.5} mb={2}>
              <Typography variant="body1">
                <strong>{payload.company_name}</strong>
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Period: {MONTHS[payload.period_month - 1]} {payload.period_year}
              </Typography>
            </Stack>

            <Button
              variant="outlined"
              component="label"
              fullWidth
              sx={{ mb: 2 }}
            >
              {file ? file.name : "Choose .xlsx file"}
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

            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={submitting || !file}
            >
              {submitting ? "Uploading…" : "Upload"}
            </Button>

            <Typography variant="caption" color="text.secondary" display="block" mt={2}>
              Link valid for {payload.expires_in_days} days.
            </Typography>
          </Box>
        )}

        {done && (
          <Box textAlign="center" py={4}>
            <CheckCircleOutlineIcon color="success" sx={{ fontSize: 56 }} />
            <Typography variant="h6" mt={2}>
              Thanks — file received.
            </Typography>
            <Typography variant="body2" color="text.secondary" mt={1}>
              Our team will review and confirm. You can close this window.
            </Typography>
          </Box>
        )}
      </Paper>
    </Container>
  );
}
