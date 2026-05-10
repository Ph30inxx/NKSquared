import { Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import AppBar from "@mui/material/AppBar";
import Avatar from "@mui/material/Avatar";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import Stack from "@mui/material/Stack";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import LogoutIcon from "@mui/icons-material/Logout";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";

import { api } from "../../api/client";
import { useAuthStore } from "../../stores/auth";
import SidebarNav from "./SidebarNav";

const DRAWER_WIDTH = 228;

interface HealthResponse {
  status: string;
  service: string;
}

function useApiHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => (await api.get<HealthResponse>("/health")).data,
    refetchInterval: 60_000,
    retry: 1,
  });
}

function initials(email?: string, role?: string): string {
  if (email) {
    const parts = email.split("@")[0].split(/[._-]/);
    return parts
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase() ?? "")
      .join("");
  }
  return role?.[0]?.toUpperCase() ?? "U";
}

export default function AppLayout() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const health = useApiHealth();

  const isChecking = health.isLoading;

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <AppBar position="fixed" color="default" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
        <Toolbar sx={{ minHeight: "56px !important", px: 2.5 }}>
          {/* Brand */}
          <Stack direction="row" alignItems="center" spacing={1} sx={{ flexGrow: 1 }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: 1.5,
                background: "linear-gradient(135deg, #4F75E8 0%, #1B4FD8 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Typography sx={{ color: "#fff", fontWeight: 800, fontSize: "0.8rem", lineHeight: 1 }}>
                NK
              </Typography>
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.02em", color: "text.primary" }}>
              NKSquared
            </Typography>
          </Stack>

          <Stack direction="row" spacing={1.5} alignItems="center">
            {/* API health dot */}
            <Tooltip
              title={
                isChecking ? "Checking API…" :
                health.isError ? "API unreachable" :
                `API: ${health.data?.status ?? "ok"}`
              }
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <FiberManualRecordIcon
                  sx={{
                    fontSize: 10,
                    color: isChecking ? "text.disabled" : health.isError ? "error.main" : "success.main",
                  }}
                />
                <Typography variant="caption" color="text.secondary" sx={{ display: { xs: "none", sm: "block" } }}>
                  {isChecking ? "checking" : health.isError ? "offline" : "online"}
                </Typography>
              </Box>
            </Tooltip>

            <Divider orientation="vertical" flexItem sx={{ my: 1 }} />

            {/* User info */}
            {user && (
              <Stack direction="row" spacing={1} alignItems="center">
                <Avatar
                  sx={{
                    width: 30,
                    height: 30,
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    bgcolor: "primary.main",
                  }}
                >
                  {initials(user.email, user.role)}
                </Avatar>
                <Box sx={{ display: { xs: "none", md: "block" } }}>
                  <Typography variant="caption" sx={{ fontWeight: 600, display: "block", lineHeight: 1.2 }}>
                    {user.email?.split("@")[0] ?? user.role}
                  </Typography>
                  <Chip
                    label={user.role}
                    size="small"
                    color="primary"
                    variant="outlined"
                    sx={{ height: 16, fontSize: "0.65rem", "& .MuiChip-label": { px: 0.75 } }}
                  />
                </Box>
              </Stack>
            )}

            <Tooltip title="Sign out">
              <Button
                color="inherit"
                size="small"
                onClick={handleLogout}
                startIcon={<LogoutIcon sx={{ fontSize: "1rem !important" }} />}
                sx={{ color: "text.secondary", fontWeight: 500, minWidth: 0 }}
              >
                <Box sx={{ display: { xs: "none", sm: "block" } }}>Sign out</Box>
              </Button>
            </Tooltip>
          </Stack>
        </Toolbar>
      </AppBar>

      <Drawer
        variant="permanent"
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: {
            width: DRAWER_WIDTH,
            boxSizing: "border-box",
            bgcolor: "background.paper",
          },
        }}
      >
        <Toolbar sx={{ minHeight: "56px !important" }} />
        <Divider />
        <Box sx={{ overflowY: "auto", overflowX: "hidden", flex: 1, py: 1 }}>
          <SidebarNav />
        </Box>
      </Drawer>

      <Box
        component="main"
        sx={{ flexGrow: 1, bgcolor: "background.default", p: 3, minWidth: 0 }}
      >
        <Toolbar sx={{ minHeight: "56px !important" }} />
        <Outlet />
      </Box>
    </Box>
  );
}
