import { useAuthStore } from "../../stores/auth";

const CHAT_BASE = "/chat-api";

function authHeader(): Record<string, string> {
  const token = useAuthStore.getState().accessToken;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Conversation types ────────────────────────────────────────────────────────

export interface Conversation {
  id: string;
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

// ── Conversation CRUD ─────────────────────────────────────────────────────────

export async function listConversations(): Promise<Conversation[]> {
  const res = await fetch(`${CHAT_BASE}/conversations`, {
    headers: authHeader(),
  });
  if (!res.ok) throw new Error(`Failed to list conversations: ${res.status}`);
  return res.json();
}

export async function createConversation(): Promise<{ id: string; session_id: string; title: string }> {
  const res = await fetch(`${CHAT_BASE}/conversations`, {
    method: "POST",
    headers: authHeader(),
  });
  if (!res.ok) throw new Error(`Failed to create conversation: ${res.status}`);
  return res.json();
}

export async function deleteConversation(id: string): Promise<void> {
  await fetch(`${CHAT_BASE}/conversations/${id}`, {
    method: "DELETE",
    headers: authHeader(),
  });
}

export async function getSessionHistory(
  sessionId: string,
): Promise<Array<{ role: string; content: string }>> {
  const res = await fetch(`${CHAT_BASE}/session/${sessionId}/history`, {
    headers: authHeader(),
  });
  if (!res.ok) throw new Error(`Failed to load history: ${res.status}`);
  const data = await res.json();
  return data.messages ?? [];
}

// ── Chat streaming ────────────────────────────────────────────────────────────

/**
 * Send a message to the chatbot via SSE streaming.
 * Calls onChunk for each streamed token, onDone when the stream closes.
 */
export async function sendMessage(
  message: string,
  sessionId: string,
  onChunk: (text: string) => void,
  onDone: () => void,
  onError: (err: string) => void,
): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${CHAT_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeader() },
      body: JSON.stringify({ message, session_id: sessionId, stream: true }),
    });
  } catch {
    onError("Could not reach the chatbot service.");
    return;
  }

  if (!res.ok) {
    onError(`Chatbot error: ${res.status}`);
    return;
  }

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const text = decoder.decode(value, { stream: true });
    for (const line of text.split("\n")) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6);
      if (payload === "[DONE]") {
        onDone();
        return;
      }
      if (payload.startsWith("[ERROR]")) {
        onError(payload.slice(8));
        return;
      }
      try {
        onChunk(JSON.parse(payload));
      } catch {
        onChunk(payload);
      }
    }
  }
  onDone();
}

/**
 * Signal that the last answer was correct (thumbs-up).
 * Sends a hidden system directive — the agent saves the validated query.
 */
export async function signalThumbsUp(
  userQuestion: string,
  sessionId: string,
): Promise<void> {
  await fetch(`${CHAT_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeader() },
    body: JSON.stringify({
      message:
        `[SYSTEM: The user confirmed the last answer was correct. ` +
        `Call save_validated_query with the SQL and explanation used to answer: ` +
        `"${userQuestion}". Reply only with a brief confirmation — no other content.]`,
      session_id: sessionId,
      stream: false,
    }),
  });
}
