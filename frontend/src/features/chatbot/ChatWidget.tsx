import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Divider from "@mui/material/Divider";
import Drawer from "@mui/material/Drawer";
import Fab from "@mui/material/Fab";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import ChatIcon from "@mui/icons-material/Chat";
import CloseIcon from "@mui/icons-material/Close";
import RefreshIcon from "@mui/icons-material/Refresh";
import SendIcon from "@mui/icons-material/Send";
import ThumbUpOutlinedIcon from "@mui/icons-material/ThumbUpOutlined";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useChatSession, ChatMessage } from "./useChatSession";

// ── Message bubble ────────────────────────────────────────────────────────────

interface MessageProps {
  message: ChatMessage;
  isStreaming: boolean;
  isLast: boolean;
  userQuestion: string;
  onThumbsUp: () => void;
}

function MessageBubble({
  message,
  isStreaming,
  isLast,
  userQuestion,
  onThumbsUp,
}: MessageProps) {
  const isUser      = message.role === "user";
  const isTyping    = isLast && isStreaming && !isUser;
  const showThumbUp = !isUser && !isTyping && !!message.content;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        mb: 1,
      }}
    >
      <Box
        sx={{
          maxWidth: "88%",
          px: 1.5,
          py: 1,
          borderRadius: 2,
          bgcolor: isUser ? "primary.main" : "grey.100",
          color: isUser ? "white" : "text.primary",
          fontSize: 13,
          lineHeight: 1.6,
          whiteSpace: isUser ? "pre-wrap" : "normal",
          wordBreak: "break-word",
          "& p": { m: 0, mb: 1, "&:last-child": { mb: 0 } },
          "& ul, & ol": { pl: 2.5, m: 0, mb: 1, mt: 0.5 },
          "& li": { mb: 0.5 },
          "& h1, & h2, & h3": { m: 0, mt: 1, mb: 0.5, fontSize: 14, fontWeight: 600 },
        }}
      >
        {isUser ? (
          message.content
        ) : message.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {message.content}
          </ReactMarkdown>
        ) : isTyping ? (
          "…"
        ) : null}
      </Box>

      {showThumbUp && (
        <Tooltip title="Mark as correct">
          <IconButton size="small" onClick={onThumbsUp} sx={{ mt: 0.25 }}>
            <ThumbUpOutlinedIcon sx={{ fontSize: 14 }} />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
}

// ── Main widget ───────────────────────────────────────────────────────────────

export default function ChatWidget() {
  const [open, setOpen]   = useState(false);
  const [input, setInput] = useState("");
  const bottomRef         = useRef<HTMLDivElement>(null);

  const { messages, isStreaming, error, send, thumbsUp, reset } = useChatSession();

  // Auto-scroll to bottom whenever messages update
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

      {/* Side panel */}
      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{
          sx: {
            width: { xs: "100%", sm: 420 },
            display: "flex",
            flexDirection: "column",
          },
        }}
      >
        {/* Header */}
        <Box
          sx={{
            px: 2,
            py: 1.5,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography variant="subtitle1" fontWeight={600}>
            NKSquared Intelligence
          </Typography>
          <Box>
            <Tooltip title="New conversation">
              <IconButton size="small" onClick={reset}>
                <RefreshIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <IconButton size="small" onClick={() => setOpen(false)}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        <Divider />

        {/* Message list */}
        <Box sx={{ flex: 1, overflowY: "auto", px: 2, py: 1.5 }}>
          {messages.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Ask anything about the portfolio or MIS data.
              <br />
              <br />
              Examples:
              <br />• "What is our overall MOIC?"
              <br />• "Show Company_01 EBITDA trend for FY26"
              <br />• "Which sectors are underperforming?"
            </Typography>
          )}

          {messages.map((msg, i) => {
            // Find the preceding user message to pass to thumbs-up
            const userQuestion =
              msg.role === "assistant" && i > 0
                ? messages[i - 1].content
                : "";

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
            disabled={isStreaming}
            variant="outlined"
          />
          <IconButton
            color="primary"
            onClick={handleSend}
            disabled={isStreaming || !input.trim()}
          >
            <SendIcon />
          </IconButton>
        </Box>
      </Drawer>
    </>
  );
}
