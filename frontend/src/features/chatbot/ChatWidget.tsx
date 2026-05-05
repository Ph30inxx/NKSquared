import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import Fab from "@mui/material/Fab";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import ChatIcon from "@mui/icons-material/Chat";
import CloseIcon from "@mui/icons-material/Close";
import MicIcon from "@mui/icons-material/Mic";
import MicOffIcon from "@mui/icons-material/MicOff";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import { useChatSession } from "./useChatSession";
import { useVoiceCall } from "./useVoiceCall";
import MessageBubble from "./MessageBubble";

export default function ChatWidget() {
  const location = useLocation();
  const [open, setOpen]   = useState(false);
  const [input, setInput] = useState("");
  const bottomRef         = useRef<HTMLDivElement>(null);

  const {
    messages, isStreaming, error, send, thumbsUp, reset,
    sessionId, appendMessage,
  } = useChatSession();

  const {
    state: voiceState,
    volume,
    transcript,
    activeActionSummary,
    start: startVoice,
    stop: stopVoice,
  } = useVoiceCall(sessionId);

  // Auto-scroll on new messages
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Surface voice transcripts into the chat message list
  useEffect(() => {
    if (transcript) {
      appendMessage({ role: "assistant", content: transcript });
    }
    // appendMessage is stable — intentionally omit transcript from deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcript]);

  // Hide widget on pages that don't need it
  if (location.pathname === "/chat") return null;
  if (location.pathname.startsWith("/upload/")) return null;
  if (location.pathname === "/login") return null;

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

  return (
    <>
      {/* Floating action button */}
      {!open && (
        <Fab
          color="primary"
          onClick={() => setOpen(true)}
          sx={{ position: "fixed", bottom: 28, right: 28, zIndex: 1300 }}
          aria-label="Open chat"
        >
          <ChatIcon />
        </Fab>
      )}

      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{
          sx: { width: { xs: "100%", sm: 420 }, display: "flex", flexDirection: "column" },
        }}
      >
        {/* Header */}
        <Box sx={{ px: 2, py: 1.5, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Typography variant="subtitle1" fontWeight={600}>
            NKSquared Intelligence
          </Typography>
          <Box>
            <Tooltip title="New conversation">
              <IconButton size="small" onClick={reset} disabled={voiceActive}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <IconButton size="small" onClick={() => setOpen(false)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        <Divider />

        {/* Voice status banner */}
        {voiceActive && (
          <Box
            sx={{
              px: 2, py: 0.75,
              display: "flex", alignItems: "center", gap: 1,
              bgcolor: "primary.50",
              borderBottom: "1px solid",
              borderColor: "primary.100",
              fontSize: 12,
              color: "primary.main",
            }}
          >
            {/* Pulsing dot */}
            <Box
              sx={{
                width: 8, height: 8, borderRadius: "50%", bgcolor: "error.main", flexShrink: 0,
                "@keyframes pulse": {
                  "0%, 100%": { opacity: 1 },
                  "50%": { opacity: 0.3 },
                },
                animation: voiceState === "active" ? "pulse 1.4s ease-in-out infinite" : "none",
              }}
            />

            {voiceState === "thinking" && "Looking up data…"}
            {voiceState === "executing" && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, flex: 1, minWidth: 0 }}>
                <CircularProgress size={11} thickness={5} color="inherit" />
                <Typography
                  variant="caption"
                  sx={{ color: "inherit", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                >
                  {activeActionSummary ? `Executing: ${activeActionSummary}` : "Executing action…"}
                </Typography>
              </Box>
            )}
            {voiceState === "active" && "Listening…"}

            <Box sx={{ ml: "auto", opacity: 0.55, fontSize: 11, flexShrink: 0 }}>
              {Math.round(volume * 100)}%
            </Box>
          </Box>
        )}

        {/* Message list */}
        <Box sx={{ flex: 1, overflowY: "auto", px: 2, py: 1.5 }}>
          {messages.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Ask anything about the portfolio or MIS data, or use the mic to speak.
              <br /><br />
              Examples:
              <br />• "What is our overall MOIC?"
              <br />• "Show Company_01 EBITDA trend for FY26"
              <br />• "Which sectors are underperforming?"
            </Typography>
          )}

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
            <Alert severity="error" sx={{ mt: 1, fontSize: 12 }}>
              {error}
            </Alert>
          )}

          <div ref={bottomRef} />
        </Box>

        <Divider />

        {/* Input bar */}
        <Box sx={{ px: 2, py: 1.5, display: "flex", gap: 1, alignItems: "flex-end" }}>
          <TextField
            fullWidth
            size="small"
            multiline
            maxRows={4}
            placeholder="Ask a question…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isStreaming || voiceActive}
            variant="outlined"
          />

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
              <IconButton
                onClick={startVoice}
                disabled={isStreaming}
                sx={{ color: "text.secondary" }}
              >
                <MicIcon />
              </IconButton>
            </Tooltip>
          )}

          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={isStreaming || !input.trim() || voiceActive}
          >
            <SendIcon />
          </IconButton>
        </Box>
      </Drawer>
    </>
  );
}
