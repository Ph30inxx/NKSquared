import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";

import { api } from "../api/client";
import { useAuthStore } from "../stores/auth";

interface HealthResponse {
  status: string;
  service: string;
}

function useApiHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => (await api.get<HealthResponse>("/health")).data,
    refetchInterval: 30_000,
    retry: 1,
  });
}

export default function Dashboard() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const health = useApiHealth();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  const apiState = health.isLoading
    ? { label: "API: checking…", color: "default" as const }
    : health.isError
      ? { label: "API: unreachable", color: "error" as const }
      : { label: `API: ${health.data?.status ?? "unknown"}`, color: "success" as const };

  return (
    <Box>
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            NKSquared
          </Typography>
          <Stack direction="row" spacing={2} alignItems="center">
            <Chip label={apiState.label} color={apiState.color} size="small" />
            {user && <Chip label={user.role} color="primary" size="small" />}
            <Button color="inherit" onClick={handleLogout}>
              Sign out
            </Button>
          </Stack>
        </Toolbar>
      </AppBar>

      <Container maxWidth="md" sx={{ py: 6 }}>
        <Paper elevation={1} sx={{ p: 4 }}>
          <Stack spacing={2}>
            <Typography variant="h4" component="h1">
              Welcome{user ? `, ${user.full_name}` : ""}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              This is your dashboard. Portfolio, MIS, and analytics modules
              will land here in upcoming sprints.
            </Typography>
            {user && (
              <Typography variant="body2" color="text.secondary">
                Signed in as <strong>{user.email}</strong>
              </Typography>
            )}
          </Stack>
        </Paper>
      </Container>
    </Box>
  );
}
