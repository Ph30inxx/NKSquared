import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Typography from "@mui/material/Typography";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import DashboardIcon from "@mui/icons-material/Dashboard";
import BusinessCenterIcon from "@mui/icons-material/BusinessCenter";
import GridOnIcon from "@mui/icons-material/GridOn";
import InboxIcon from "@mui/icons-material/Inbox";
import RuleIcon from "@mui/icons-material/Rule";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import HistoryIcon from "@mui/icons-material/History";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import LogoutIcon from "@mui/icons-material/Logout";
import AddIcon from "@mui/icons-material/Add";

import { useChatSession } from "./useChatSession";
import { useVoiceCall } from "./useVoiceCall";
import { useAuthStore } from "../../stores/auth";

const APP_NAV = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon fontSize="small" />, end: true },
  { to: "/portfolio", label: "Portfolio", icon: <BusinessCenterIcon fontSize="small" /> },
  { to: "/grid", label: "Grid", icon: <GridOnIcon fontSize="small" /> },
  { to: "/mis", label: "MIS", icon: <InboxIcon fontSize="small" /> },
  { to: "/mis/templates", label: "MIS Templates", icon: <RuleIcon fontSize="small" /> },
  { to: "/admin/reminders", label: "Reminders", icon: <NotificationsActiveIcon fontSize="small" /> },
  { to: "/admin/audit-log", label: "Audit Log", icon: <HistoryIcon fontSize="small" /> },
];

const STATE_LABELS: Record<string, string> = {
  idle: "Tap to start",
  connecting: "Connecting…",
  active: "Listening…",
  thinking: "Looking up data…",
  executing: "Executing action…",
  ending: "Ending call…",
};

export default function VoicePage() {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const { sessionId, newChat } = useChatSession();
  const { state: voiceState, volume, transcript, start: startVoice, stop: stopVoice } =
    useVoiceCall(sessionId);

  // Accumulate transcript lines
  const [transcriptLines, setTranscriptLines] = useState<string[]>([]);
  const transcriptRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (transcript) {
      setTranscriptLines((prev) => [...prev.slice(-19), transcript]);
    }
  }, [transcript]);

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [transcriptLines]);

  const isActive    = voiceState === "active" || voiceState === "thinking" || voiceState === "executing";
  const isConnecting = voiceState === "connecting";
  const isLive      = voiceState === "active" || voiceState === "ending";

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const handleMic = () => {
    if (isActive || voiceState === "ending") {
      stopVoice();
    } else if (!isConnecting) {
      startVoice();
    }
  };

  return (
    <Box sx={{ display: "flex", height: "100vh", overflow: "hidden", bgcolor: "background.default" }}>

      {/* ── Left Sidebar ──────────────────────────────────────────────────────── */}
      <Box
        sx={{
          width: 260,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
        }}
      >
        {/* App name */}
        <Box sx={{ px: 2.5, py: 2 }}>
          <Typography variant="h6" fontWeight={700} sx={{ letterSpacing: -0.3 }}>
            NKSquared
          </Typography>
        </Box>

        <Divider />

        {/* Navigation shortcuts */}
        <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
          <ListItemButton
            component={NavLink}
            to="/chat"
            sx={{
              borderRadius: 2,
              px: 1.5,
              gap: 1,
              color: "text.secondary",
              "&:hover": { bgcolor: "action.hover" },
            }}
          >
            <AddIcon fontSize="small" />
            <Typography variant="body2" fontWeight={500}>New Conversation</Typography>
          </ListItemButton>
        </Box>

        <Box sx={{ px: 1.5, pb: 1 }}>
          <ListItemButton
            component={NavLink}
            to="/voice"
            sx={{
              borderRadius: 2,
              px: 1.5,
              gap: 1,
              "&.active": { color: "primary.main", bgcolor: "action.selected" },
              color: "text.secondary",
            }}
          >
            <GraphicEqIcon fontSize="small" />
            <Typography variant="body2" fontWeight={500}>Voice Tools</Typography>
          </ListItemButton>
        </Box>

        <Divider />

        {/* Spacer */}
        <Box sx={{ flex: 1 }} />

        <Divider />

        {/* App Navigation */}
        <Box>
          <Typography
            variant="caption"
            sx={{
              px: 2, pt: 1.5, pb: 0.5,
              display: "block",
              color: "text.disabled",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: 0.6,
              fontSize: "0.65rem",
            }}
          >
            App Navigation
          </Typography>
          <List dense disablePadding sx={{ pb: 0.5 }}>
            {APP_NAV.map((item) => (
              <ListItemButton
                key={item.to}
                component={NavLink}
                to={item.to}
                end={item.end}
                sx={{
                  mx: 0.5,
                  borderRadius: 1,
                  "&.active": {
                    bgcolor: "action.selected",
                    "& .MuiListItemIcon-root, & .MuiListItemText-primary": {
                      color: "primary.main",
                      fontWeight: 600,
                    },
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 32 }}>{item.icon}</ListItemIcon>
                <ListItemText
                  primary={item.label}
                  primaryTypographyProps={{ variant: "body2" }}
                />
              </ListItemButton>
            ))}
          </List>

          <Divider />

          <ListItemButton
            onClick={handleLogout}
            sx={{ mx: 0.5, borderRadius: 1, my: 0.5, color: "text.secondary" }}
          >
            <ListItemIcon sx={{ minWidth: 32 }}>
              <LogoutIcon fontSize="small" />
            </ListItemIcon>
            <ListItemText primary="Sign out" primaryTypographyProps={{ variant: "body2" }} />
          </ListItemButton>
        </Box>
      </Box>

      {/* ── Voice Main Area ────────────────────────────────────────────────────── */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 4,
          px: 4,
        }}
      >
        {/* Title */}
        <Box sx={{ textAlign: "center" }}>
          <Typography variant="h5" fontWeight={700} gutterBottom>
            Voice Assistant
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Give Cortex a natural language command to take action.
          </Typography>
        </Box>

        {/* Mic button */}
        <Box
          sx={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {/* Ripple rings when active */}
          {isActive && (
            <>
              {[1, 2].map((i) => (
                <Box
                  key={i}
                  sx={{
                    position: "absolute",
                    width: 88 + i * 24,
                    height: 88 + i * 24,
                    borderRadius: "50%",
                    border: "2px solid",
                    borderColor: "primary.main",
                    opacity: 0.25 / i,
                    "@keyframes ripple": {
                      "0%": { transform: "scale(1)", opacity: 0.3 / i },
                      "100%": { transform: `scale(${1 + i * 0.15})`, opacity: 0 },
                    },
                    animation: `ripple ${1.2 + i * 0.3}s ease-out infinite`,
                  }}
                />
              ))}
            </>
          )}

          {isConnecting ? (
            <Box
              sx={{
                width: 88, height: 88,
                borderRadius: "50%",
                bgcolor: "primary.main",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <CircularProgress size={32} sx={{ color: "white" }} />
            </Box>
          ) : (
            <IconButton
              onClick={handleMic}
              disabled={voiceState === "ending"}
              sx={{
                width: 88,
                height: 88,
                bgcolor: isActive ? "error.main" : "primary.main",
                color: "white",
                "&:hover": {
                  bgcolor: isActive ? "error.dark" : "primary.dark",
                  transform: "scale(1.05)",
                },
                "&.Mui-disabled": {
                  bgcolor: "action.disabledBackground",
                },
                transition: "all 0.2s ease",
                boxShadow: isActive
                  ? "0 0 0 4px rgba(211,47,47,0.2)"
                  : "0 4px 20px rgba(0,0,0,0.15)",
              }}
            >
              {isActive || voiceState === "ending" ? (
                <MicOffIcon sx={{ fontSize: 36 }} />
              ) : (
                <MicIcon sx={{ fontSize: 36 }} />
              )}
            </IconButton>
          )}
        </Box>

        {/* Status label */}
        <Box sx={{ textAlign: "center", minHeight: 48 }}>
          <Typography
            variant="body1"
            fontWeight={500}
            color={isActive ? "primary.main" : "text.secondary"}
          >
            {STATE_LABELS[voiceState] ?? ""}
          </Typography>
          {isActive && (
            <Typography variant="caption" color="text.disabled">
              Volume: {Math.round(volume * 100)}%
            </Typography>
          )}
        </Box>

        {/* Transcript display */}
        {transcriptLines.length > 0 && (
          <Box
            ref={transcriptRef}
            sx={{
              width: "100%",
              maxWidth: 560,
              maxHeight: 220,
              overflowY: "auto",
              bgcolor: "background.paper",
              borderRadius: 3,
              border: "1px solid",
              borderColor: "divider",
              p: 2.5,
              display: "flex",
              flexDirection: "column",
              gap: 1,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mb: 0.5 }}>
              <ChatBubbleOutlineIcon sx={{ fontSize: 14, color: "text.disabled" }} />
              <Typography variant="caption" color="text.disabled" fontWeight={600} letterSpacing={0.5}>
                ASSISTANT TRANSCRIPT
              </Typography>
            </Box>
            {transcriptLines.map((line, i) => (
              <Typography
                key={i}
                variant="body2"
                sx={{
                  color: i === transcriptLines.length - 1 ? "text.primary" : "text.secondary",
                  opacity: 0.4 + (i / transcriptLines.length) * 0.6,
                  lineHeight: 1.6,
                }}
              >
                {line}
              </Typography>
            ))}
          </Box>
        )}

        {transcriptLines.length === 0 && !isActive && (
          <Typography variant="body2" color="text.disabled" sx={{ opacity: 0.6 }}>
            Assistant speech will appear here
          </Typography>
        )}
      </Box>
    </Box>
  );
}
