import { useEffect, useRef, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemButton from "@mui/material/ListItemButton";
import ListItemIcon from "@mui/material/ListItemIcon";
import ListItemText from "@mui/material/ListItemText";
import Menu from "@mui/material/Menu";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import MoreHorizIcon from "@mui/icons-material/MoreHoriz";
import PushPinIcon from "@mui/icons-material/PushPin";
import PushPinOutlinedIcon from "@mui/icons-material/PushPinOutlined";
import SendIcon from "@mui/icons-material/Send";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import DashboardIcon from "@mui/icons-material/Dashboard";
import BusinessCenterIcon from "@mui/icons-material/BusinessCenter";
import GridOnIcon from "@mui/icons-material/GridOn";
import InboxIcon from "@mui/icons-material/Inbox";
import RuleIcon from "@mui/icons-material/Rule";
import NotificationsActiveIcon from "@mui/icons-material/NotificationsActive";
import HistoryIcon from "@mui/icons-material/History";
import GraphicEqIcon from "@mui/icons-material/GraphicEq";
import LogoutIcon from "@mui/icons-material/Logout";

import { useChatSession } from "./useChatSession";
import { useVoiceCall } from "./useVoiceCall";
import MessageBubble from "./MessageBubble";
import { useAuthStore } from "../../stores/auth";
import type { Conversation } from "./chatApi";

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupByDate(conversations: Conversation[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday.getTime() - 86_400_000);
  const startOfLastWeek = new Date(startOfToday.getTime() - 7 * 86_400_000);

  const groups: { label: string; items: Conversation[] }[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Last 7 Days", items: [] },
    { label: "Older", items: [] },
  ];

  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    if (d >= startOfToday) groups[0].items.push(conv);
    else if (d >= startOfYesterday) groups[1].items.push(conv);
    else if (d >= startOfLastWeek) groups[2].items.push(conv);
    else groups[3].items.push(conv);
  }

  return groups.filter((g) => g.items.length > 0);
}

const APP_NAV = [
  { to: "/", label: "Dashboard", icon: <DashboardIcon fontSize="small" />, end: true },
  { to: "/ai-dashboard", label: "AI Reports", icon: <AutoAwesomeIcon fontSize="small" /> },
  { to: "/portfolio", label: "Portfolio", icon: <BusinessCenterIcon fontSize="small" /> },
  { to: "/grid", label: "Grid", icon: <GridOnIcon fontSize="small" /> },
  { to: "/mis", label: "MIS", icon: <InboxIcon fontSize="small" /> },
  { to: "/mis/templates", label: "MIS Templates", icon: <RuleIcon fontSize="small" /> },
  { to: "/admin/reminders", label: "Reminders", icon: <NotificationsActiveIcon fontSize="small" /> },
  { to: "/admin/audit-log", label: "Audit Log", icon: <HistoryIcon fontSize="small" /> },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [hoveredConvId, setHoveredConvId] = useState<string | null>(null);
  const [menuAnchor, setMenuAnchor] = useState<{ el: HTMLElement; convId: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);

  const {
    conversations,
    activeConvId,
    messages,
    isStreaming,
    error,
    loadingConvs,
    send,
    thumbsUp,
    newChat,
    selectConversation,
    removeConversation,
    sessionId,
    appendMessage,
    pinnedIds,
    togglePin,
  } = useChatSession();

  const {
    state: voiceState,
    volume,
    turns,
    activeActionSummary,
    start: startVoice,
    stop: stopVoice,
  } = useVoiceCall(sessionId);

  // Sync voice turns into the chat message list as they arrive.
  // Both user speech and assistant replies are appended so the inline
  // chat thread shows the full voice exchange alongside text messages.
  const prevTurnsLen = useRef(0);
  useEffect(() => {
    const newTurns = turns.slice(prevTurnsLen.current);
    newTurns.forEach((t) => appendMessage({ role: t.role, content: t.content }));
    prevTurnsLen.current = turns.length;
  }, [turns, appendMessage]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isStreaming) return;
    setInput("");
    send(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const voiceActive = voiceState === "active" || voiceState === "thinking" || voiceState === "executing";
  const voiceBusy   = voiceState === "connecting" || voiceState === "thinking" || voiceState === "executing";
  const voiceLive   = voiceState === "active" || voiceState === "ending";

  const pinnedConvs = conversations.filter((c) => pinnedIds.has(c.id));
  const unpinnedConvs = conversations.filter((c) => !pinnedIds.has(c.id));
  const groups = groupByDate(unpinnedConvs);

  const renderConvItem = (conv: Conversation) => {
    const isHovered = hoveredConvId === conv.id;
    const isPinned = pinnedIds.has(conv.id);
    const isActive = conv.id === activeConvId;
    const isMenuOpen = menuAnchor?.convId === conv.id;

    return (
      <ListItem
        key={conv.id}
        disablePadding
        onMouseEnter={() => setHoveredConvId(conv.id)}
        onMouseLeave={() => setHoveredConvId(null)}
        sx={{ position: "relative" }}
      >
        <ListItemButton
          selected={isActive}
          onClick={() => selectConversation(conv)}
          sx={{
            borderRadius: 1.5,
            mx: 0.75,
            py: 0.75,
            pr: isHovered || isMenuOpen ? 4.5 : isPinned ? 3 : 1.5,
            "&.Mui-selected": {
              bgcolor: "action.selected",
              "&:hover": { bgcolor: "action.selected" },
            },
          }}
        >
          <ListItemText
            primary={conv.title}
            primaryTypographyProps={{
              noWrap: true,
              variant: "body2",
              fontWeight: isActive ? 600 : 400,
            }}
          />
        </ListItemButton>

        {/* Pin badge — always visible when pinned and not hovered */}
        {isPinned && !isHovered && !isMenuOpen && (
          <Box
            sx={{
              position: "absolute",
              right: 14,
              top: "50%",
              transform: "translateY(-50%)",
              pointerEvents: "none",
            }}
          >
            <PushPinIcon sx={{ fontSize: 12, color: "primary.main", opacity: 0.65 }} />
          </Box>
        )}

        {/* ⋯ button — visible on hover or when menu is open */}
        {(isHovered || isMenuOpen) && (
          <Box
            sx={{
              position: "absolute",
              right: 6,
              top: "50%",
              transform: "translateY(-50%)",
            }}
          >
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                setMenuAnchor({ el: e.currentTarget, convId: conv.id });
              }}
              sx={{
                width: 26,
                height: 26,
                color: "text.secondary",
                bgcolor: isMenuOpen ? "action.selected" : "transparent",
                "&:hover": { bgcolor: "action.hover", color: "text.primary" },
              }}
            >
              <MoreHorizIcon sx={{ fontSize: 16 }} />
            </IconButton>
          </Box>
        )}
      </ListItem>
    );
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
        {/* Brand */}
        <Box sx={{ px: 2, py: 1.5, display: "flex", alignItems: "center", gap: 1 }}>
          <Box
            sx={{
              width: 28, height: 28, borderRadius: 1.5, flexShrink: 0,
              background: "linear-gradient(135deg, #4F75E8 0%, #1B4FD8 100%)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}
          >
            <Typography sx={{ color: "#fff", fontWeight: 800, fontSize: "0.75rem", lineHeight: 1 }}>
              NK
            </Typography>
          </Box>
          <Typography variant="h6" fontWeight={700} sx={{ letterSpacing: -0.3 }}>
            NKSquared
          </Typography>
        </Box>

        <Divider />

        {/* New Chat button */}
        <Box sx={{ px: 1.5, pt: 1.5, pb: 1 }}>
          <Button
            fullWidth
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={newChat}
            sx={{
              borderRadius: 2,
              justifyContent: "flex-start",
              textTransform: "none",
              fontWeight: 500,
            }}
          >
            New Conversation
          </Button>
        </Box>

        {/* Voice Tools link */}
        <Box sx={{ px: 1.5, pb: 1 }}>
          <Button
            fullWidth
            component={NavLink}
            to="/voice"
            startIcon={<GraphicEqIcon />}
            sx={{
              borderRadius: 2,
              justifyContent: "flex-start",
              textTransform: "none",
              fontWeight: 500,
              color: "text.secondary",
              "&:hover": { bgcolor: "action.hover" },
              "&.active": { color: "primary.main", bgcolor: "action.selected" },
            }}
          >
            Voice Tools
          </Button>
        </Box>

        <Divider />

        {/* Conversation list — scrollable */}
        <Box sx={{ flex: 1, overflowY: "auto", minHeight: 0 }}>
          {loadingConvs ? (
            <Box sx={{ display: "flex", justifyContent: "center", pt: 4 }}>
              <CircularProgress size={22} />
            </Box>
          ) : conversations.length === 0 ? (
            <Box sx={{ p: 3, textAlign: "center" }}>
              <ChatBubbleOutlineIcon sx={{ color: "text.disabled", fontSize: 32, mb: 1 }} />
              <Typography variant="body2" color="text.secondary">
                No conversations yet
              </Typography>
            </Box>
          ) : (
            <>
              {/* Pinned section */}
              {pinnedConvs.length > 0 && (
                <>
                  <Typography
                    variant="caption"
                    sx={{
                      px: 2, pt: 1.5, pb: 0.5,
                      display: "flex", alignItems: "center", gap: 0.5,
                      color: "text.disabled",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: 0.6,
                      fontSize: "0.65rem",
                    }}
                  >
                    <PushPinIcon sx={{ fontSize: 11 }} /> Pinned
                  </Typography>
                  <List dense disablePadding>
                    {pinnedConvs.map(renderConvItem)}
                  </List>
                  <Divider sx={{ my: 1 }} />
                </>
              )}

              {/* Recent (unpinned) section */}
              {unpinnedConvs.length > 0 && (
                <>
                  <Typography
                    variant="caption"
                    sx={{
                      px: 2, pt: pinnedConvs.length > 0 ? 0.5 : 1.5, pb: 0.5,
                      display: "block",
                      color: "text.disabled",
                      fontWeight: 700,
                      textTransform: "uppercase",
                      letterSpacing: 0.6,
                      fontSize: "0.65rem",
                    }}
                  >
                    Recent
                  </Typography>
                  {groups.map((group) => (
                    <Box key={group.label}>
                      <Typography
                        variant="caption"
                        sx={{
                          px: 2, pt: 1, pb: 0.5,
                          display: "block",
                          color: "text.disabled",
                          fontSize: "0.6rem",
                          letterSpacing: 0.4,
                        }}
                      >
                        {group.label}
                      </Typography>
                      <List dense disablePadding>
                        {group.items.map(renderConvItem)}
                      </List>
                    </Box>
                  ))}
                </>
              )}
            </>
          )}
        </Box>

        {/* Conversation context menu */}
        <Menu
          anchorEl={menuAnchor?.el}
          open={Boolean(menuAnchor)}
          onClose={() => setMenuAnchor(null)}
          onClick={() => setMenuAnchor(null)}
          transformOrigin={{ horizontal: "right", vertical: "top" }}
          anchorOrigin={{ horizontal: "right", vertical: "bottom" }}
          slotProps={{
            paper: {
              elevation: 3,
              sx: { minWidth: 160, borderRadius: 2, border: "1px solid", borderColor: "divider" },
            },
          }}
        >
          <MenuItem
            onClick={() => {
              if (menuAnchor) togglePin(menuAnchor.convId);
            }}
            sx={{ gap: 1.5, py: 1 }}
          >
            {menuAnchor && pinnedIds.has(menuAnchor.convId) ? (
              <>
                <PushPinIcon sx={{ fontSize: 16, color: "primary.main" }} />
                <Typography variant="body2">Unpin</Typography>
              </>
            ) : (
              <>
                <PushPinOutlinedIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                <Typography variant="body2">Pin</Typography>
              </>
            )}
          </MenuItem>
          <MenuItem
            onClick={() => {
              if (menuAnchor) removeConversation(menuAnchor.convId);
            }}
            sx={{ gap: 1.5, py: 1, color: "error.main" }}
          >
            <DeleteOutlineIcon sx={{ fontSize: 16 }} />
            <Typography variant="body2" color="error.main">Delete</Typography>
          </MenuItem>
        </Menu>

        <Divider />

        {/* App Navigation — fixed at bottom */}
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
            <ListItemText
              primary="Sign out"
              primaryTypographyProps={{ variant: "body2" }}
            />
          </ListItemButton>
        </Box>
      </Box>

      {/* ── Chat Area ─────────────────────────────────────────────────────────── */}
      <Paper
        elevation={0}
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          borderRadius: 0,
          bgcolor: "background.default",
        }}
      >
        {/* Header */}
        <Box
          sx={{
            px: 3, py: 1.5,
            borderBottom: "1px solid",
            borderColor: "divider",
            display: "flex",
            alignItems: "center",
            gap: 1,
            bgcolor: "background.paper",
          }}
        >
          <ChatBubbleOutlineIcon fontSize="small" sx={{ color: "text.secondary" }} />
          <Typography variant="subtitle1" fontWeight={600}>
            {conversations.find((c) => c.id === activeConvId)?.title ?? "New conversation"}
          </Typography>
        </Box>

        {/* Voice status banner */}
        {voiceActive && (
          <Box
            sx={{
              px: 3, py: 1.5,
              display: "flex", alignItems: "center", gap: 1.5,
              bgcolor: (t) => `${t.palette.primary.main}12`,
              borderBottom: "1px solid",
              borderColor: (t) => `${t.palette.primary.main}28`,
              fontSize: 13,
              color: "primary.main",
            }}
          >
            <Box
              sx={{
                width: 10, height: 10, borderRadius: "50%", bgcolor: "error.main", flexShrink: 0,
                "@keyframes pulse": { "0%, 100%": { opacity: 1 }, "50%": { opacity: 0.3 } },
                animation: voiceState === "active" ? "pulse 1.4s ease-in-out infinite" : "none",
              }}
            />
            {voiceState === "thinking" && "Looking up data…"}
            {voiceState === "executing" && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, flex: 1, minWidth: 0 }}>
                <CircularProgress size={14} thickness={5} color="inherit" />
                <Typography variant="body2" sx={{ color: "inherit", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {activeActionSummary ? `Executing: ${activeActionSummary}` : "Executing action…"}
                </Typography>
              </Box>
            )}
            {voiceState === "active" && "Listening…"}
            <Box sx={{ ml: "auto", opacity: 0.55, fontSize: 12, flexShrink: 0 }}>
              Volume: {Math.round(volume * 100)}%
            </Box>
          </Box>
        )}

        {/* Messages */}
        <Box sx={{ flex: 1, overflowY: "auto", p: 3 }}>
          {messages.length === 0 && !loadingConvs && (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                opacity: 0.7,
              }}
            >
              <Typography variant="h6" color="text.secondary" gutterBottom>
                How can I help you today?
              </Typography>
              <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 400 }}>
                Ask anything about the portfolio, MIS data, revenue trends, or alert status.
              </Typography>
            </Box>
          )}

          <Container maxWidth="md" disableGutters>
            {messages.map((msg, i) => {
              const userQuestion =
                msg.role === "assistant" && i > 0 ? messages[i - 1].content : "";
              return (
                <MessageBubble
                  key={i}
                  message={msg}
                  isStreaming={isStreaming}
                  isLast={i === messages.length - 1}
                  userQuestion={userQuestion}
                  onThumbsUp={() => thumbsUp(userQuestion)}
                />
              );
            })}
            {error && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {error}
              </Alert>
            )}
            <div ref={bottomRef} />
          </Container>
        </Box>

        {/* Input */}
        <Box
          sx={{
            p: 2,
            bgcolor: "background.paper",
            borderTop: "1px solid",
            borderColor: "divider",
          }}
        >
          <Container
            maxWidth="md"
            disableGutters
            sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}
          >
            <TextField
              fullWidth
              multiline
              maxRows={6}
              placeholder="Message the NKSquared Analyst..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming || voiceActive}
              variant="outlined"
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 3,
                  bgcolor: "background.default",
                },
              }}
            />
            <Box sx={{ pb: 0.5, display: "flex", alignItems: "center", gap: 0.5 }}>
              {voiceBusy ? (
                <Box sx={{ display: "flex", alignItems: "center", px: 0.5 }}>
                  <CircularProgress size={22} />
                </Box>
              ) : voiceLive ? (
                <Tooltip title="End voice call">
                  <IconButton color="error" onClick={stopVoice}>
                    <MicOffIcon />
                  </IconButton>
                </Tooltip>
              ) : (
                <Tooltip title="Start voice call">
                  <IconButton onClick={startVoice} disabled={isStreaming} sx={{ color: "text.secondary" }}>
                    <MicIcon />
                  </IconButton>
                </Tooltip>
              )}
              <IconButton
                color="primary"
                onClick={handleSend}
                disabled={isStreaming || !input.trim() || voiceActive}
                sx={{
                  bgcolor: "primary.main",
                  color: "white",
                  "&:hover": { bgcolor: "primary.dark" },
                  "&.Mui-disabled": {
                    bgcolor: "action.disabledBackground",
                    color: "action.disabled",
                  },
                }}
              >
                <SendIcon />
              </IconButton>
            </Box>
          </Container>
        </Box>
      </Paper>
    </Box>
  );
}
