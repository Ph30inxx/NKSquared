import { useState, useCallback } from "react";
import { sendMessage, signalThumbsUp } from "./chatApi";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const SESSION_KEY = "nk_chat_session_id";

function getOrCreateSessionId(): string {
  let id = localStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

export function useChatSession() {
  const [sessionId]   = useState<string>(getOrCreateSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError]       = useState<string | null>(null);

  const send = useCallback(
    async (userMessage: string) => {
      setError(null);
      setMessages((prev) => [
        ...prev,
        { role: "user", content: userMessage },
        { role: "assistant", content: "" },
      ]);
      setIsStreaming(true);

      await sendMessage(
        userMessage,
        sessionId,
        (chunk) => {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + chunk },
            ];
          });
        },
        () => setIsStreaming(false),
        (err) => {
          setError(err);
          setIsStreaming(false);
        },
      );
    },
    [sessionId],
  );

  const thumbsUp = useCallback(
    (userQuestion: string) => {
      signalThumbsUp(userQuestion, sessionId).catch(() => {
        // thumbs-up is best-effort — silently ignore failures
      });
    },
    [sessionId],
  );

  const reset = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    window.location.reload();
  }, []);

  return { messages, isStreaming, error, send, thumbsUp, sessionId, reset };
}
