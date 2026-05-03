import { useEffect, useRef, useState } from "react";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Alert from "@mui/material/Alert";
import Paper from "@mui/material/Paper";
import SendIcon from "@mui/icons-material/Send";
import RefreshIcon from "@mui/icons-material/Refresh";
import Tooltip from "@mui/material/Tooltip";

import { useChatSession } from "./useChatSession";
import MessageBubble from "./MessageBubble";

export default function ChatPage() {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

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
    <Box sx={{ display: "flex", flexDirection: "column", height: "calc(100vh - 120px)" }}>
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h5" fontWeight={600}>
          AI Assistant
        </Typography>
        <Tooltip title="New conversation">
          <IconButton onClick={reset} color="primary">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Chat Area */}
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
          bgcolor: "background.default"
        }}
      >
        {/* Messages List */}
        <Box sx={{ flex: 1, overflowY: "auto", p: 3 }}>
          {messages.length === 0 && (
            <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", opacity: 0.7 }}>
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
              const userQuestion = msg.role === "assistant" && i > 0 ? messages[i - 1].content : "";
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

        {/* Input Area */}
        <Box sx={{ p: 2, bgcolor: "background.paper", borderTop: "1px solid", borderColor: "divider" }}>
          <Container maxWidth="md" disableGutters sx={{ display: "flex", gap: 1, alignItems: "flex-end" }}>
            <TextField
              fullWidth
              multiline
              maxRows={6}
              placeholder="Message the NKSquared Analyst..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isStreaming}
              variant="outlined"
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: 3,
                  bgcolor: "background.default",
                }
              }}
            />
            <Box sx={{ pb: 0.5 }}>
              <IconButton
                color="primary"
                onClick={handleSend}
                disabled={isStreaming || !input.trim()}
                sx={{ 
                  bgcolor: "primary.main", 
                  color: "white", 
                  "&:hover": { bgcolor: "primary.dark" },
                  "&.Mui-disabled": { bgcolor: "action.disabledBackground", color: "action.disabled" }
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
