import { useEffect, useRef, useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import IconButton from "@mui/material/IconButton";
import List from "@mui/material/List";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import Paper from "@mui/material/Paper";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import DownloadIcon from "@mui/icons-material/Download";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import PictureAsPdfIcon from "@mui/icons-material/PictureAsPdf";
import SendIcon from "@mui/icons-material/Send";
import SyncIcon from "@mui/icons-material/Sync";

import { type DashboardJob, type SSEEvent, directDownload, fetchHistory, startGeneration } from "./dashboardApi";

// ── Tool label map ────────────────────────────────────────────────────────────
const TOOL_LABELS: Record<string, string> = {
  resolve_period: "Resolving time period",
  get_portfolio_aggregates: "Fetching portfolio KPIs",
  get_portfolio_summary: "Fetching portfolio summary",
  get_entity_breakdown: "Fetching entity breakdown",
  get_company_detail: "Fetching company profile",
  get_transaction_timeline: "Fetching transaction history",
  get_cap_table_snapshot: "Fetching cap table",
  get_valuation_history: "Fetching valuation history",
  calculate_irr: "Computing IRR",
  check_portfolio_alerts: "Checking portfolio alerts",
  get_company_trend: "Fetching P&L trend",
  get_mis_recent_summary: "Fetching recent MIS summary",
  get_cost_breakdown: "Fetching cost structure",
  get_bu_breakdown: "Fetching BU breakdown",
  get_channel_breakdown: "Fetching channel mix",
  get_outlet_breakdown: "Fetching outlet data",
  get_outlet_profitability: "Fetching outlet profitability",
  get_mis_submission_status: "Checking MIS compliance",
  get_mis_anomaly_summary: "Fetching data anomalies",
  run_query: "Running custom query",
  convert_forex: "Converting currency",
  create_kpi_cards: "Generating KPI cards",
  create_combo_chart: "Generating P&L chart",
  create_bar_chart: "Generating bar chart",
  create_line_chart: "Generating trend chart",
  create_pie_chart: "Generating pie chart",
  create_waterfall_chart: "Generating waterfall chart",
  create_scatter_chart: "Generating portfolio map",
  create_stacked_area_chart: "Generating composition chart",
  create_table_image: "Generating data table",
  _compile_dashboard: "Compiling PDF",
  compile_dashboard: "Compiling PDF",
};

const EXAMPLE_PROMPTS = [
  "Portfolio overview for FY26 with sector MOIC breakdown",
  "Company_02 BU-wise revenue trends and channel mix for FY26",
  "Cost structure analysis for Company_01 with P&L waterfall",
  "Full FY26 report: portfolio KPIs, company trends, outlet profitability",
];

type PageState = "idle" | "generating" | "ready" | "error";

interface ProgressEntry {
  tool: string;
  status: "running" | "done";
  label: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function AIDashboardPage() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState<PageState>("idle");
  const [progressLog, setProgressLog] = useState<ProgressEntry[]>([]);
  const [readyInfo, setReadyInfo] = useState<SSEEvent | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [history, setHistory] = useState<DashboardJob[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [generationSecs, setGenerationSecs] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Load history on mount
  useEffect(() => {
    loadHistory();
  }, []);

  // Auto-scroll progress log
  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [progressLog]);

  // Generation timer
  useEffect(() => {
    if (state === "generating") {
      setGenerationSecs(0);
      timerRef.current = setInterval(() => setGenerationSecs((s) => s + 1), 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [state]);

  async function loadHistory() {
    setLoadingHistory(true);
    try {
      const jobs = await fetchHistory();
      setHistory(jobs);
    } catch {
      // ignore
    } finally {
      setLoadingHistory(false);
    }
  }

  async function handleGenerate() {
    const q = query.trim();
    if (!q || state === "generating") return;

    setState("generating");
    setProgressLog([]);
    setReadyInfo(null);
    setErrorMsg(null);

    try {
      const res = await startGeneration(q);
      if (!res.ok) {
        throw new Error(`Server error ${res.status}`);
      }
      if (!res.body) {
        throw new Error("No response body");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          let event: SSEEvent;
          try {
            event = JSON.parse(line.slice(6));
          } catch {
            continue;
          }

          if (event.type === "tool_call" && event.tool) {
            const label = TOOL_LABELS[event.tool] ?? event.tool;
            setProgressLog((prev) => {
              const existing = prev.findIndex((p) => p.tool === event.tool && p.status === "running");
              if (event.status === "done" && existing >= 0) {
                const updated = [...prev];
                updated[existing] = { ...updated[existing], status: "done" };
                return updated;
              }
              if (event.status === "running") {
                return [...prev, { tool: event.tool!, status: "running", label }];
              }
              return [...prev, { tool: event.tool!, status: event.status ?? "done", label }];
            });
          } else if (event.type === "complete") {
            setReadyInfo(event);
            setState("ready");
            loadHistory();
          } else if (event.type === "error") {
            setErrorMsg(event.message ?? "Generation failed");
            setState("error");
          }
        }
      }

      // If stream ended without complete/error, check final state
      if (state === "generating") {
        setState("error");
        setErrorMsg("Stream ended unexpectedly");
      }
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Unknown error");
      setState("error");
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleGenerate();
    }
  }

  return (
    <Box sx={{ display: "flex", height: "100%", gap: 0, overflow: "hidden" }}>

      {/* ── Left panel ─────────────────────────────────────────────────────── */}
      <Box
        sx={{
          width: 380,
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          borderRight: "1px solid",
          borderColor: "divider",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <Box sx={{ px: 3, py: 2.5, borderBottom: "1px solid", borderColor: "divider" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 0.5 }}>
            <AutoAwesomeIcon sx={{ color: "primary.main", fontSize: 20 }} />
            <Typography variant="h6" fontWeight={700}>
              AI Dashboard
            </Typography>
          </Box>
          <Typography variant="body2" color="text.secondary">
            Describe the report you want — the AI will fetch data, generate charts, and compile a PDF.
          </Typography>
        </Box>

        {/* Query input */}
        <Box sx={{ px: 3, pt: 2.5, pb: 2 }}>
          <TextField
            fullWidth
            multiline
            rows={4}
            placeholder="e.g. Give me a full portfolio overview for FY26 with sector breakdown, Company_02 BU trends, and outlet profitability…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={state === "generating"}
            variant="outlined"
            sx={{
              mb: 1.5,
              "& .MuiOutlinedInput-root": { borderRadius: 2 },
            }}
          />

          <Button
            fullWidth
            variant="contained"
            size="large"
            startIcon={state === "generating" ? <CircularProgress size={18} color="inherit" /> : <SendIcon />}
            onClick={handleGenerate}
            disabled={!query.trim() || state === "generating"}
            sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600, py: 1.2 }}
          >
            {state === "generating" ? `Generating… ${generationSecs}s` : "Generate Dashboard"}
          </Button>
        </Box>

        {/* Example prompts */}
        <Box sx={{ px: 3, pb: 2 }}>
          <Typography variant="caption" color="text.disabled" fontWeight={700}
            sx={{ textTransform: "uppercase", letterSpacing: 0.5, display: "block", mb: 1 }}>
            Example requests
          </Typography>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 0.75 }}>
            {EXAMPLE_PROMPTS.map((p) => (
              <Chip
                key={p}
                label={p}
                size="small"
                variant="outlined"
                clickable
                onClick={() => setQuery(p)}
                disabled={state === "generating"}
                sx={{
                  height: "auto",
                  py: 0.5,
                  "& .MuiChip-label": { whiteSpace: "normal", fontSize: "0.72rem" },
                  borderRadius: 1.5,
                  justifyContent: "flex-start",
                  textAlign: "left",
                }}
              />
            ))}
          </Box>
        </Box>

        <Divider />

        {/* History */}
        <Box sx={{ flex: 1, overflowY: "auto", px: 2, pt: 1.5 }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1, px: 1 }}>
            <Typography variant="caption" color="text.disabled" fontWeight={700}
              sx={{ textTransform: "uppercase", letterSpacing: 0.5 }}>
              History
            </Typography>
            <Tooltip title="Refresh">
              <IconButton size="small" onClick={loadHistory} disabled={loadingHistory}>
                <SyncIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>

          {loadingHistory ? (
            <Box sx={{ display: "flex", justifyContent: "center", pt: 2 }}>
              <CircularProgress size={20} />
            </Box>
          ) : history.length === 0 ? (
            <Typography variant="body2" color="text.secondary" sx={{ px: 1, pt: 1 }}>
              No dashboards generated yet.
            </Typography>
          ) : (
            <List dense disablePadding>
              {history.map((job) => (
                <ListItem
                  key={job.dashboard_id}
                  disablePadding
                  sx={{
                    px: 1, py: 0.5, borderRadius: 1.5, mb: 0.5,
                    "&:hover": { bgcolor: "action.hover" },
                  }}
                  secondaryAction={
                    job.status === "ready" ? (
                      <Tooltip title="Download PDF">
                        <IconButton
                          size="small"
                          onClick={() => directDownload(job.dashboard_id, job.title)}
                        >
                          <DownloadIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    ) : job.status === "generating" ? (
                      <CircularProgress size={16} />
                    ) : null
                  }
                >
                  <ListItemText
                    primary={job.title || "Untitled Dashboard"}
                    secondary={
                      (job.created_at ? new Date(job.created_at).toLocaleDateString() : "") +
                      (job.page_count ? ` · ${job.page_count} pages` : "") +
                      (job.status === "failed" ? " · Failed" : "")
                    }
                    primaryTypographyProps={{ variant: "body2", noWrap: true, fontWeight: 500 }}
                    secondaryTypographyProps={{ variant: "caption" }}
                  />
                </ListItem>
              ))}
            </List>
          )}
        </Box>
      </Box>

      {/* ── Right panel ────────────────────────────────────────────────────── */}
      <Box sx={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", p: 3 }}>

        {/* Idle state */}
        {state === "idle" && (
          <Box
            sx={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              opacity: 0.6,
            }}
          >
            <PictureAsPdfIcon sx={{ fontSize: 56, color: "text.disabled", mb: 2 }} />
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Your dashboard will appear here
            </Typography>
            <Typography variant="body2" color="text.secondary" align="center" sx={{ maxWidth: 380 }}>
              Describe the report you need on the left and click Generate.
              The AI will fetch portfolio data, draw charts, and compile a PDF.
            </Typography>
          </Box>
        )}

        {/* Generating state — progress log */}
        {(state === "generating" || (state !== "idle" && progressLog.length > 0 && state !== "ready")) && state !== "error" && (
          <Paper
            variant="outlined"
            sx={{
              flex: 1,
              overflow: "hidden",
              display: "flex",
              flexDirection: "column",
              borderRadius: 2,
            }}
          >
            <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <CircularProgress size={18} />
                <Typography variant="subtitle2" fontWeight={600}>
                  Generating dashboard… {generationSecs}s
                </Typography>
              </Box>
              <Typography variant="caption" color="text.secondary">
                The agent is fetching data and building your charts.
              </Typography>
            </Box>

            <Box sx={{ flex: 1, overflowY: "auto", px: 3, py: 2 }}>
              {progressLog.map((entry, i) => (
                <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 1 }}>
                  {entry.status === "done" ? (
                    <CheckCircleIcon sx={{ fontSize: 16, color: "success.main", flexShrink: 0 }} />
                  ) : (
                    <SyncIcon sx={{ fontSize: 16, color: "primary.main", flexShrink: 0,
                      "@keyframes spin": { "100%": { transform: "rotate(360deg)" } },
                      animation: "spin 1.2s linear infinite" }} />
                  )}
                  <Typography
                    variant="body2"
                    color={entry.status === "done" ? "text.secondary" : "text.primary"}
                    sx={{ fontWeight: entry.status === "running" ? 500 : 400 }}
                  >
                    {entry.label}
                  </Typography>
                </Box>
              ))}
              <div ref={logEndRef} />
            </Box>
          </Paper>
        )}

        {/* Ready state */}
        {state === "ready" && readyInfo && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Paper
              variant="outlined"
              sx={{
                p: 3,
                borderRadius: 2,
                borderColor: "success.main",
                bgcolor: "success.50",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "flex-start", gap: 2 }}>
                <CheckCircleIcon sx={{ color: "success.main", fontSize: 28, mt: 0.3 }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="h6" fontWeight={700} gutterBottom>
                    Dashboard Ready
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    <strong>{readyInfo.title || "Dashboard"}</strong>
                    {readyInfo.page_count ? ` · ${readyInfo.page_count} pages` : ""}
                    {` · Generated in ${generationSecs}s`}
                  </Typography>
                  {readyInfo.summary && (
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1, lineHeight: 1.7 }}>
                      {readyInfo.summary}
                    </Typography>
                  )}
                  <Button
                    variant="contained"
                    color="success"
                    startIcon={<DownloadIcon />}
                    onClick={() => directDownload(readyInfo.dashboard_id!, readyInfo.title ?? "dashboard")}
                    sx={{ mt: 2, textTransform: "none", fontWeight: 600, borderRadius: 2 }}
                  >
                    Download PDF
                  </Button>
                </Box>
              </Box>
            </Paper>

            {/* Progress log review */}
            {progressLog.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 2, maxHeight: 240, overflowY: "auto" }}>
                <Typography variant="caption" color="text.disabled" fontWeight={700}
                  sx={{ textTransform: "uppercase", letterSpacing: 0.5, display: "block", mb: 1 }}>
                  Steps completed
                </Typography>
                {progressLog.map((entry, i) => (
                  <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.75 }}>
                    <CheckCircleIcon sx={{ fontSize: 14, color: "success.main", flexShrink: 0 }} />
                    <Typography variant="body2" color="text.secondary">{entry.label}</Typography>
                  </Box>
                ))}
              </Paper>
            )}
          </Box>
        )}

        {/* Error state */}
        {state === "error" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <Alert
              severity="error"
              icon={<ErrorOutlineIcon />}
              action={
                <Button color="inherit" size="small" onClick={() => { setState("idle"); setErrorMsg(null); setProgressLog([]); }}>
                  Try Again
                </Button>
              }
            >
              <Typography variant="subtitle2" fontWeight={600}>Generation Failed</Typography>
              <Typography variant="body2">{errorMsg}</Typography>
            </Alert>

            {progressLog.length > 0 && (
              <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
                <Typography variant="caption" color="text.disabled" fontWeight={700}
                  sx={{ textTransform: "uppercase", letterSpacing: 0.5, display: "block", mb: 1 }}>
                  Steps completed before failure
                </Typography>
                {progressLog.map((entry, i) => (
                  <Box key={i} sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.75 }}>
                    {entry.status === "done"
                      ? <CheckCircleIcon sx={{ fontSize: 14, color: "success.main", flexShrink: 0 }} />
                      : <HourglassEmptyIcon sx={{ fontSize: 14, color: "warning.main", flexShrink: 0 }} />
                    }
                    <Typography variant="body2" color="text.secondary">{entry.label}</Typography>
                  </Box>
                ))}
              </Paper>
            )}
          </Box>
        )}
      </Box>
    </Box>
  );
}
