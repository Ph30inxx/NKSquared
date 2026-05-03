const CHAT_BASE = "/chat-api";

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
      headers: { "Content-Type": "application/json" },
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

  const reader  = res.body!.getReader();
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
        const decoded = JSON.parse(payload);
        onChunk(decoded);
      } catch {
        // Fallback for non-json or partial lines
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
    headers: { "Content-Type": "application/json" },
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
