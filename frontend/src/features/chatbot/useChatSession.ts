import { useCallback, useEffect, useRef, useState } from "react";
import {
  Conversation,
  createConversation,
  deleteConversation,
  getSessionHistory,
  listConversations,
  sendMessage,
  signalThumbsUp,
} from "./chatApi";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export function useChatSession() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadingConvs, setLoadingConvs] = useState(true);

  // Stable ref so delete handler always sees latest conversations without
  // recreating other callbacks that depend on it.
  const convsRef = useRef<Conversation[]>([]);
  convsRef.current = conversations;

  const selectConversation = useCallback(async (conv: Conversation) => {
    setActiveConvId(conv.id);
    setSessionId(conv.session_id);
    setMessages([]);
    setError(null);

    // New conversations have no Agno session yet — nothing to load
    if (conv.title === "New Conversation") return;

    try {
      const history = await getSessionHistory(conv.session_id);
      const mapped: ChatMessage[] = history
        .filter((m) => m.role === "user" || m.role === "assistant")
        .map((m) => ({
          role: m.role as "user" | "assistant",
          content: typeof m.content === "string" ? m.content : String(m.content ?? ""),
        }));
      setMessages(mapped);
    } catch (err) {
      setError(`Could not load conversation history: ${err instanceof Error ? err.message : err}`);
    }
  }, []);

  const newChat = useCallback(async () => {
    try {
      const conv = await createConversation();
      const newConv: Conversation = {
        ...conv,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setConversations((prev) => [newConv, ...prev]);
      setActiveConvId(conv.id);
      setSessionId(conv.session_id);
      setMessages([]);
      setError(null);
    } catch {
      // Fallback: generate a local session if API is unreachable
      setSessionId(crypto.randomUUID());
      setActiveConvId(null);
      setMessages([]);
      setError(null);
    }
  }, []);

  // Load conversation list once on mount
  const initialized = useRef(false);
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    listConversations()
      .then(async (convs) => {
        setConversations(convs);
        if (convs.length > 0) {
          await selectConversation(convs[0]);
        } else {
          await newChat();
        }
      })
      .catch(async () => {
        // If auth/network fails, still allow using chat
        await newChat();
      })
      .finally(() => setLoadingConvs(false));
  }, [selectConversation, newChat]);

  const removeConversation = useCallback(
    async (convId: string) => {
      await deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));

      // If the deleted one was active, switch to the next available
      if (activeConvId === convId) {
        const remaining = convsRef.current.filter((c) => c.id !== convId);
        if (remaining.length > 0) {
          setTimeout(() => selectConversation(remaining[0]), 0);
        } else {
          setTimeout(() => newChat(), 0);
        }
      }
    },
    [activeConvId, selectConversation, newChat],
  );

  const send = useCallback(
    async (userMessage: string) => {
      if (!sessionId) return;
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
            return [...prev.slice(0, -1), { ...last, content: last.content + chunk }];
          });
        },
        () => {
          setIsStreaming(false);
          // Optimistically update title + timestamp in sidebar
          setConversations((prev) =>
            prev.map((c) => {
              if (c.session_id !== sessionId) return c;
              return {
                ...c,
                title: c.title === "New Conversation" ? userMessage.slice(0, 60) : c.title,
                updated_at: new Date().toISOString(),
              };
            }),
          );
        },
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
      signalThumbsUp(userQuestion, sessionId).catch(() => {});
    },
    [sessionId],
  );

  return {
    conversations,
    activeConvId,
    messages,
    isStreaming,
    error,
    loadingConvs,
    sessionId,
    send,
    thumbsUp,
    newChat,
    selectConversation,
    removeConversation,
  };
}
