import { useCallback, useEffect, useRef, useState } from "react";
import Vapi from "@vapi-ai/web";
import { startVoiceSession } from "./chatApi";

export type VoiceState =
  | "idle"
  | "connecting"
  | "active"
  | "thinking"    // query_investment_data tool fired — looking up data
  | "executing"   // execute_investment_action tool fired — write in progress
  | "ending";

export interface UseVoiceCallReturn {
  state: VoiceState;
  volume: number;
  transcript: string | null;
  activeActionSummary: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

export function useVoiceCall(sessionId: string): UseVoiceCallReturn {
  const vapiRef = useRef<Vapi | null>(null);
  const [state, setState] = useState<VoiceState>("idle");
  const [volume, setVolume] = useState(0);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [activeActionSummary, setActiveActionSummary] = useState<string | null>(null);

  const start = useCallback(async () => {
    setState("connecting");
    try {
      const { vapi_public_key, assistant_id, user_id } =
        await startVoiceSession(sessionId);

      const vapi = new Vapi(vapi_public_key);
      vapiRef.current = vapi;

      vapi.on("call-start", () => setState("active"));
      vapi.on("call-end", () => {
        setState("idle");
        setVolume(0);
        setTranscript(null);
        setActiveActionSummary(null);
      });
      vapi.on("error", (e: any) => {
        console.error("Vapi error:", e);
        setState("idle");
        setVolume(0);
        setTranscript(null);
        setActiveActionSummary(null);
      });
      vapi.on("volume-level", (v: number) => setVolume(v));

      vapi.on("message", (msg: any) => {
        if (msg.type === "tool-calls") {
          const tc = msg.toolCallList?.[0];
          // Vapi sends name/arguments at the top level; some versions
          // wrap them under a "function" key (OpenAI-style).
          const toolName =
            tc?.function?.name ?? tc?.name ?? "";
          if (toolName === "execute_investment_action") {
            // Verbal confirmation already happened before this fires.
            // Show what is being executed rather than asking for confirmation.
            try {
              const rawArgs = tc?.function?.arguments ?? tc?.arguments ?? "{}";
              const args =
                typeof rawArgs === "string" ? JSON.parse(rawArgs) : rawArgs;
              setActiveActionSummary(args.action_summary ?? null);
            } catch {
              setActiveActionSummary(null);
            }
            setState("executing");
          } else {
            setActiveActionSummary(null);
            setState("thinking");
          }
        }

        if (msg.type === "conversation-update") {
          setState("active");
          setActiveActionSummary(null);
          // Surface latest assistant utterance as a chat transcript entry
          const turns: any[] = msg.conversation ?? [];
          const lastAssistant = [...turns]
            .reverse()
            .find((t) => t.role === "assistant");
          if (lastAssistant?.content) {
            setTranscript(
              typeof lastAssistant.content === "string"
                ? lastAssistant.content
                : JSON.stringify(lastAssistant.content)
            );
          }
        }
      });

      await vapi.start(assistant_id, {
        variableValues: {
          user_id: String(user_id),
          session_id: sessionId,
        },
      });
    } catch (err) {
      setState("idle");
      throw err;
    }
  }, [sessionId]);

  const stop = useCallback(() => {
    vapiRef.current?.stop();
    setState("ending");
  }, []);

  // Cleanup on unmount to prevent orphaned calls (e.g. during Vite HMR or navigation)
  useEffect(() => {
    return () => {
      if (vapiRef.current) {
        vapiRef.current.stop();
      }
    };
  }, []);

  return { state, volume, transcript, activeActionSummary, start, stop };
}
