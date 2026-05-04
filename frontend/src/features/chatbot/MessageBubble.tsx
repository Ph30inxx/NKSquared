import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import ThumbUpOutlinedIcon from "@mui/icons-material/ThumbUpOutlined";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { keyframes } from "@mui/system";
import { ChatMessage } from "./useChatSession";

const bounce = keyframes`
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
`;

function TypingIndicator() {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5, height: 24, px: 1 }}>
      <Box sx={{ width: 6, height: 6, bgcolor: "text.secondary", borderRadius: "50%", animation: `${bounce} 1.4s infinite ease-in-out both`, animationDelay: "-0.32s" }} />
      <Box sx={{ width: 6, height: 6, bgcolor: "text.secondary", borderRadius: "50%", animation: `${bounce} 1.4s infinite ease-in-out both`, animationDelay: "-0.16s" }} />
      <Box sx={{ width: 6, height: 6, bgcolor: "text.secondary", borderRadius: "50%", animation: `${bounce} 1.4s infinite ease-in-out both` }} />
    </Box>
  );
}

interface MessageProps {
  message: ChatMessage;
  isStreaming: boolean;
  isLast: boolean;
  userQuestion: string;
  onThumbsUp: () => void;
}

export default function MessageBubble({
  message,
  isStreaming,
  isLast,
  userQuestion,
  onThumbsUp,
}: MessageProps) {
  const isUser = message.role === "user";
  const isTyping = isLast && isStreaming && !isUser;
  const showThumbUp = !isUser && !isTyping && !!message.content;

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: isUser ? "flex-end" : "flex-start",
        mb: 2,
      }}
    >
      <Box
        sx={{
          maxWidth: "80%",
          px: 2,
          py: 1.5,
          borderRadius: 3,
          bgcolor: isUser ? "primary.main" : "background.paper",
          color: isUser ? "white" : "text.primary",
          boxShadow: isUser ? "none" : 1,
          fontSize: 14,
          lineHeight: 1.6,
          whiteSpace: isUser ? "pre-wrap" : "normal",
          wordBreak: "break-word",
          "& p": { m: 0, mb: 1.5, "&:last-child": { mb: 0 } },
          "& ul, & ol": { pl: 3, m: 0, mb: 1.5, mt: 0.5 },
          "& li": { mb: 0.5 },
          "& h1, & h2, & h3": { m: 0, mt: 1.5, mb: 1, fontSize: 16, fontWeight: 600 },
          "& hr": { my: 1.5, border: "none", borderTop: "1px solid", borderColor: "divider" },
          "& table": { borderCollapse: "collapse", width: "100%", mb: 1.5 },
          "& th, & td": { border: "1px solid", borderColor: "divider", px: 1.5, py: 1, textAlign: "left", fontSize: 13 },
          "& th": { bgcolor: "action.hover", fontWeight: 600 },
          "& tr:nth-of-type(even)": { bgcolor: "action.hover" },
        }}
      >
        {isUser ? (
          message.content
        ) : message.content ? (
          <ReactMarkdown 
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex]}
          >
            {message.content
              .replace(/\\\[/g, "$$")
              .replace(/\\\]/g, "$$")
              .replace(/\\\(/g, "$")
              .replace(/\\\)/g, "$")}
          </ReactMarkdown>
        ) : isTyping ? (
          <TypingIndicator />
        ) : null}
      </Box>

      {showThumbUp && (
        <Tooltip title="Mark as correct">
          <IconButton size="small" onClick={onThumbsUp} sx={{ mt: 0.5, ml: 1 }}>
            <ThumbUpOutlinedIcon sx={{ fontSize: 16 }} />
          </IconButton>
        </Tooltip>
      )}
    </Box>
  );
}
