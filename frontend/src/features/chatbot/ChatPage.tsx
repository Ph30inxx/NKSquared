import { useEffect, useRef, useState } from "react";
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
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import AddIcon from "@mui/icons-material/Add";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SendIcon from "@mui/icons-material/Send";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";

import { useChatSession } from "./useChatSession";
import { useVoiceCall } from "./useVoiceCall";
import MessageBubble from "./MessageBubble";
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

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  const [input, setInput] = useState("");
  const [hoveredConvId, setHoveredConvId] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

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
  } = useChatSession();

  const {
    state: voiceState,
    volume,
    transcript,
    activeActionSummary,
    start: startVoice,
    stop: stopVoice,
  } = useVoiceCall(sessionId);

  // Surface voice transcripts into the chat message list
  useEffect(() => {
    if (transcript) {
      appendMessage({ role: "assistant", content: transcript });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcript]);

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

  const voiceActive   = voiceState === "active" || voiceState === "thinking" || voiceState === "executing";
  const voiceBusy     = voiceState === "connecting" || voiceState === "thinking" || voiceState === "executing";
  const voiceLive     = voiceState === "active" || voiceState === "ending";

  const groups = groupByDate(conversations);

  return (
    <Box sx={{ display: "flex", height: "calc(100vh - 120px)", overflow: "hidden" }}>

      {/* ── Left Sidebar ──────────────────────────────────────────────── */}
      <Box
        sx={{
          width: 260,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid",
          borderColor: "divider",
          bgcolor: "background.paper",
          mr: 2,
        }}
      >
        {/* New Chat button */}
        <Box sx={{ p: 1.5 }}>
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
            New Chat
          </Button>
        </Box>

        <Divider />

        {/* Conversation list */}
        <Box sx={{ flex: 1, overflowY: "auto" }}>
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
            groups.map((group) => (
              <Box key={group.label}>
                <Typography
                  variant="caption"
                  sx={{
                    px: 2,
                    pt: 1.5,
                    pb: 0.5,
                    display: "block",
                    color: "text.disabled",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: 0.6,
                    fontSize: "0.65rem",
                  }}
                >
                  {group.label}
                </Typography>
                <List dense disablePadding>
                  {group.items.map((conv) => (
                    <ListItem
                      key={conv.id}
                      disablePadding
                      secondaryAction={
                        hoveredConvId === conv.id ? (
                          <Tooltip title="Delete">
                            <IconButton
                              size="small"
                              edge="end"
                              onClick={(e) => {
                                e.stopPropagation();
                                removeConversation(conv.id);
                              }}
                              sx={{
                                color: "text.secondary",
                                mr: 0.5,
                                "&:hover": { color: "error.main" },
                              }}
                            >
                              <DeleteOutlineIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        ) : null
                      }
                      onMouseEnter={() => setHoveredConvId(conv.id)}
                      onMouseLeave={() => setHoveredConvId(null)}
                    >
                      <ListItemButton
                        selected={conv.id === activeConvId}
                        onClick={() => selectConversation(conv)}
                        sx={{
                          borderRadius: 1,
                          mx: 0.5,
                          pr: hoveredConvId === conv.id ? 5 : 1,
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
                            fontWeight: conv.id === activeConvId ? 600 : 400,
                          }}
                        />
                      </ListItemButton>
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))
          )}
        </Box>
      </Box>

      {/* ── Chat Area ─────────────────────────────────────────────────── */}
      <Paper
        elevation={0}
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 2,
          bgcolor: "background.default",
        }}
      >
        {/* Voice status banner */}
        {voiceActive && (
          <Box
            sx={{
              px: 3, py: 1.5,
              display: "flex", alignItems: "center", gap: 1.5,
              bgcolor: "primary.50",
              borderBottom: "1px solid",
              borderColor: "primary.100",
              fontSize: 13,
              color: "primary.main",
            }}
          >
            {/* Pulsing dot */}
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
              <Typography
                variant="body2"
                color="text.secondary"
                align="center"
                sx={{ maxWidth: 400 }}
              >
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
              {/* Mic button */}
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
