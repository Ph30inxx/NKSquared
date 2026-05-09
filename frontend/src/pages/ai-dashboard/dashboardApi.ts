import { useAuthStore } from "../../stores/auth";

// All dashboard requests go through Vite's /chat-api proxy
// (rewritten to http://chatbot:8001 on the server side, same as chatApi.ts).
// Never use VITE_CHATBOT_URL directly — the browser can't resolve Docker hostnames.
const DASHBOARD_BASE = "/chat-api/dashboard";

function authHeaders(): HeadersInit {
  const token = useAuthStore.getState().accessToken;
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export interface DashboardJob {
  dashboard_id: string;
  title: string;
  status: "pending" | "generating" | "ready" | "failed";
  page_count: number | null;
  created_at: string | null;
  completed_at: string | null;
  download_url: string | null;
}

export interface SSEEvent {
  type: "started" | "tool_call" | "complete" | "error" | "heartbeat";
  dashboard_id?: string;
  tool?: string;
  status?: "running" | "done";
  chart_id?: string;
  download_url?: string;
  title?: string;
  page_count?: number;
  summary?: string;
  message?: string;
}

export async function startGeneration(query: string): Promise<Response> {
  return fetch(`${DASHBOARD_BASE}/generate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ query }),
  });
}

export async function fetchHistory(): Promise<DashboardJob[]> {
  const res = await fetch(`${DASHBOARD_BASE}/history`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("Failed to load history");
  const data = await res.json();
  return data.dashboards as DashboardJob[];
}

export function directDownload(dashboardId: string, title: string): void {
  const token = useAuthStore.getState().accessToken;
  fetch(`${DASHBOARD_BASE}/${dashboardId}/download`, {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then((r) => r.blob())
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${title || "dashboard"}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    });
}
