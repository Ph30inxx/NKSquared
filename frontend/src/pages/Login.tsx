import { useState, type FormEvent } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import EmailOutlinedIcon from "@mui/icons-material/EmailOutlined";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";

import { getMe, login } from "../api/auth";
import { useAuthStore } from "../stores/auth";

interface LocationState {
  from?: string;
}

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const tokens = await login(email, password);
      setTokens(tokens.access_token, tokens.refresh_token);
      const user = await getMe();
      setUser(user);
      const from = (location.state as LocationState | null)?.from ?? "/";
      navigate(from, { replace: true });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Login failed. Check your credentials and try again.";
      setError(detail);
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
      <Box sx={{ width: "100%", maxWidth: 400 }}>
        {/* Brand mark */}
        <Stack alignItems="center" spacing={1.5} sx={{ mb: 4 }}>
          <Box
            sx={{
              width: 52,
              height: 52,
              borderRadius: 3,
              background: "linear-gradient(135deg, #4F75E8 0%, #1B4FD8 60%, #1340B0 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 8px 24px rgba(27, 79, 216, 0.35)",
            }}
          >
            <Typography sx={{ color: "#fff", fontWeight: 800, fontSize: "1.1rem", letterSpacing: "-0.02em" }}>
              NK
            </Typography>
          </Box>
          <Box textAlign="center">
            <Typography variant="h5" sx={{ fontWeight: 800, letterSpacing: "-0.03em" }}>
              NKSquared
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
              Investment intelligence platform
            </Typography>
          </Box>
        </Stack>

        <Paper
          sx={{
            p: { xs: 3, sm: 4 },
            boxShadow: "0 20px 60px rgba(0,0,0,0.10), 0 4px 16px rgba(0,0,0,0.06)",
            border: "none",
          }}
        >
          <Typography variant="h6" sx={{ mb: 0.5, fontWeight: 700 }}>
            Welcome back
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Sign in to your account to continue.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2.5 }}>
              {error}
            </Alert>
          )}

          <Stack spacing={2.5} component="form" onSubmit={handleSubmit}>
            <TextField
              label="Email address"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              fullWidth
              autoFocus
              size="medium"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <EmailOutlinedIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                  </InputAdornment>
                ),
              }}
            />
            <TextField
              label="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              fullWidth
              size="medium"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <LockOutlinedIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                  </InputAdornment>
                ),
              }}
            />
            <Button
              type="submit"
              variant="contained"
              size="large"
              fullWidth
              disabled={submitting}
              sx={{ mt: 0.5, py: 1.25, fontSize: "0.9375rem" }}
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>
          </Stack>
        </Paper>

        <Typography variant="caption" color="text.disabled" textAlign="center" display="block" sx={{ mt: 3 }}>
          © {new Date().getFullYear()} NKSquared. All rights reserved.
        </Typography>
      </Box>
    </Box>
  );
}
