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

export interface VoiceTurn {
  role: "user" | "assistant";
  content: string;
}

export interface UseVoiceCallReturn {
  state: VoiceState;
  volume: number;
  turns: VoiceTurn[];
  activeActionSummary: string | null;
  start: () => Promise<void>;
  stop: () => void;
}

export function useVoiceCall(
  sessionId: string,
  onCallEnded?: (turns: VoiceTurn[]) => void,
): UseVoiceCallReturn {
  const vapiRef = useRef<Vapi | null>(null);
  const [state, setState] = useState<VoiceState>("idle");
  const [volume, setVolume] = useState(0);
  const [turns, setTurns] = useState<VoiceTurn[]>([]);
  const [activeActionSummary, setActiveActionSummary] = useState<string | null>(null);

  // Stable refs so event handlers always see latest values without stale closures
  const turnsRef = useRef<VoiceTurn[]>([]);
  turnsRef.current = turns;
  const onCallEndedRef = useRef(onCallEnded);
  onCallEndedRef.current = onCallEnded;
  // Vapi can fire both call-end and error on the same termination — guard against double-fire
  const callEndedRef = useRef(false);

  const start = useCallback(async () => {
    setState("connecting");
    setTurns([]);
    callEndedRef.current = false;
    try {
      const { vapi_public_key, assistant_id, user_id } =
        await startVoiceSession(sessionId);

      const vapi = new Vapi(vapi_public_key);
      vapiRef.current = vapi;

      vapi.on("call-start", () => setState("active"));

      const fireCallEnded = () => {
        if (callEndedRef.current) return;
        callEndedRef.current = true;
        setState("idle");
        setVolume(0);
        setActiveActionSummary(null);
        onCallEndedRef.current?.(turnsRef.current);
      };

      vapi.on("call-end", fireCallEnded);

      vapi.on("error", (e: any) => {
        console.error("Vapi error:", e);
        fireCallEnded();
      });

      vapi.on("volume-level", (v: number) => setVolume(v));

      vapi.on("message", (msg: any) => {
        if (msg.type === "tool-calls") {
          const tc = msg.toolCallList?.[0];
          const toolName = tc?.function?.name ?? tc?.name ?? "";
          if (toolName === "execute_investment_action") {
            try {
              const rawArgs = tc?.function?.arguments ?? tc?.arguments ?? "{}";
              const args = typeof rawArgs === "string" ? JSON.parse(rawArgs) : rawArgs;
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
          // conversation-update gives the full array of turns so far.
          // Assistant tool-call turns have content: null — exclude them
          // so only spoken utterances appear in the transcript.
          const allTurns: VoiceTurn[] = (msg.conversation ?? [])
            .filter((t: any) => t.role === "user" || t.role === "assistant")
            .map((t: any) => ({
              role: t.role as "user" | "assistant",
              content: typeof t.content === "string"
                ? t.content
                : t.content != null
                  ? JSON.stringify(t.content)
                  : "",
            }))
            .filter((t: VoiceTurn) => t.content.trim() !== "");
          setTurns(allTurns);
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

  return { state, volume, turns, activeActionSummary, start, stop };
}
