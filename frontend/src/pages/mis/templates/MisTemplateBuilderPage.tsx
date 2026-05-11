import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Step from "@mui/material/Step";
import StepLabel from "@mui/material/StepLabel";
import Stepper from "@mui/material/Stepper";
import Switch from "@mui/material/Switch";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import DeleteIcon from "@mui/icons-material/Delete";

import {
  METRIC_CODES,
  MisRowMapping,
  TemplateCandidatesResponse,
  TemplateDryRunResponse,
  dryRunTemplate,
  extractCandidates,
  useCreateTemplate,
  useTemplate,
  useUpdateTemplate,
} from "../../../api/misTemplates";

const STEPS = ["Upload sample file", "Map rows to metrics", "Verify & save"];

export default function MisTemplateBuilderPage() {
  const navigate = useNavigate();
  const { id } = useParams<{ id?: string }>();
  const editingId = id ? Number(id) : null;
  const editing = useTemplate(editingId);

  const [activeStep, setActiveStep] = useState(0);
  const [file, setFile] = useState<File | null>(null);
  const [candidates, setCandidates] = useState<TemplateCandidatesResponse | null>(null);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);

  const [name, setName] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [sheetPattern, setSheetPattern] = useState("");
  const [headerRow, setHeaderRow] = useState(2);
  const [isDefault, setIsDefault] = useState(false);
  const [mappings, setMappings] = useState<MisRowMapping[]>([]);

  const [dryRun, setDryRun] = useState<TemplateDryRunResponse | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);
  const [dryRunning, setDryRunning] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const create = useCreateTemplate();
  const update = useUpdateTemplate(editingId ?? 0);

  useEffect(() => {
    if (editing.data) {
      setName(editing.data.name);
      setCompanyId(editing.data.company_id ?? "");
      setSheetPattern(editing.data.sheet_name_pattern ?? "");
      setHeaderRow(editing.data.header_row);
      setIsDefault(editing.data.is_default);
      setMappings(editing.data.row_mappings ?? []);
    }
  }, [editing.data]);

  async function handleExtract() {
    if (!file) return;
    setExtracting(true);
    setExtractError(null);
    try {
      const result = await extractCandidates(file, {
        header_row: headerRow,
      });
      setCandidates(result);
      if (!sheetPattern) {
        setSheetPattern(`^${result.selected_sheet}$`);
      }
      setActiveStep(1);
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : "Could not extract candidate rows";
      setExtractError(message);
    } finally {
      setExtracting(false);
    }
  }

  function addMapping(row: { row_index: number; label: string }) {
    setMappings((prev) => [
      ...prev,
      {
        label_regex: `^${escapeRegex(row.label)}$`,
        metric_code: "revenue_lacs",
        geography: "consolidated",
        bu_id: null,
        label_col_index: 1,
      },
    ]);
  }

  function updateMapping(idx: number, patch: Partial<MisRowMapping>) {
    setMappings((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, ...patch } : m)),
    );
  }

  function removeMapping(idx: number) {
    setMappings((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSaveAndDryRun() {
    if (!name.trim()) {
      setDryRunError("Name is required");
      return;
    }
    if (mappings.length === 0) {
      setDryRunError("Add at least one row mapping");
      return;
    }
    setDryRunError(null);
    setDryRunning(true);
    try {
      const payload = {
        name,
        company_id: companyId || null,
        is_default: isDefault,
        sheet_name_pattern: sheetPattern || null,
        header_row: headerRow,
        period_orientation: "columns" as const,
        row_mappings: mappings,
      };
      const saved = editingId
        ? await update.mutateAsync(payload)
        : await create.mutateAsync(payload);
      if (file) {
        try {
          const result = await dryRunTemplate(
            saved.id,
            file,
            companyId || undefined,
          );
          setDryRun(result);
        } catch (e: unknown) {
          const message =
            e instanceof Error ? e.message : "Dry-run failed";
          setDryRunError(message);
        }
      }
      setActiveStep(2);
    } catch (e: unknown) {
      const message =
        e instanceof Error ? e.message : "Could not save template";
      setDryRunError(message);
    } finally {
      setDryRunning(false);
    }
  }

  if (editing.isLoading && editingId) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" component="h1">
          {editingId ? `Edit template #${editingId}` : "New MIS template"}
        </Typography>
        <Button onClick={() => navigate("/mis/templates")}>Back to list</Button>
      </Stack>

      <Stepper activeStep={activeStep}>
        {STEPS.map((s) => (
          <Step key={s}>
            <StepLabel>{s}</StepLabel>
          </Step>
        ))}
      </Stepper>

      <Paper sx={{ p: 3 }}>
        <Stack spacing={2}>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="Template name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              fullWidth
            />
            <TextField
              label="Company code (optional)"
              value={companyId}
              onChange={(e) => setCompanyId(e.target.value)}
              placeholder="company_03"
              fullWidth
            />
          </Stack>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="Sheet name pattern (regex)"
              value={sheetPattern}
              onChange={(e) => setSheetPattern(e.target.value)}
              placeholder="^MIS Report.*$"
              fullWidth
            />
            <TextField
              label="Header row (1-based)"
              type="number"
              value={headerRow}
              onChange={(e) => setHeaderRow(Math.max(1, Number(e.target.value)))}
              sx={{ width: 200 }}
            />
            <FormControlLabel
              control={
                <Switch
                  checked={isDefault}
                  onChange={(_, v) => setIsDefault(v)}
                />
              }
              label="Set as default for company"
            />
          </Stack>
          <Divider />

          <Box>
            <Typography variant="subtitle2" gutterBottom>
              Step 1 — Upload a sample workbook
            </Typography>
            <Stack direction="row" spacing={2} alignItems="center">
              <Button
                variant="outlined"
                onClick={() => fileInputRef.current?.click()}
              >
                {file ? `Selected: ${file.name}` : "Choose .xlsx file"}
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                style={{ display: "none" }}
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              <Button
                variant="contained"
                onClick={handleExtract}
                disabled={!file || extracting}
              >
                {extracting ? "Reading…" : "Extract row labels"}
              </Button>
            </Stack>
            {extractError && (
              <Alert severity="error" sx={{ mt: 2 }}>
                {extractError}
              </Alert>
            )}
            {candidates && (
              <Box mt={2}>
                <Typography variant="caption" color="text.secondary">
                  Sheet <code>{candidates.selected_sheet}</code> has{" "}
                  {candidates.period_columns.length} period columns and{" "}
                  {candidates.rows.length} candidate rows.
                </Typography>
              </Box>
            )}
          </Box>
        </Stack>
      </Paper>

      {candidates && (
        <Stack direction={{ xs: "column", lg: "row" }} spacing={2}>
          <Paper sx={{ p: 2, flex: 1, maxHeight: 500, overflow: "auto" }}>
            <Typography variant="subtitle1" gutterBottom>
              Candidate rows
            </Typography>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Row</TableCell>
                  <TableCell>Label</TableCell>
                  <TableCell align="right">Add</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {candidates.rows.map((row) => (
                  <TableRow key={row.row_index}>
                    <TableCell>{row.row_index + 1}</TableCell>
                    <TableCell>
                      <Box>
                        <strong>{row.label}</strong>
                      </Box>
                      <Box color="text.secondary" fontSize="0.8em">
                        {row.sample_values.filter((v) => v != null).join(" · ")}
                      </Box>
                    </TableCell>
                    <TableCell align="right">
                      <Button size="small" onClick={() => addMapping(row)}>
                        Map
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </Paper>

          <Paper sx={{ p: 2, flex: 1.5, maxHeight: 500, overflow: "auto" }}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1">Mappings ({mappings.length})</Typography>
            </Stack>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Regex</TableCell>
                  <TableCell>Metric</TableCell>
                  <TableCell>Geo</TableCell>
                  <TableCell>BU</TableCell>
                  <TableCell />
                </TableRow>
              </TableHead>
              <TableBody>
                {mappings.map((m, idx) => (
                  <TableRow key={idx}>
                    <TableCell sx={{ minWidth: 200 }}>
                      <TextField
                        size="small"
                        value={m.label_regex}
                        onChange={(e) =>
                          updateMapping(idx, { label_regex: e.target.value })
                        }
                        fullWidth
                      />
                    </TableCell>
                    <TableCell>
                      <FormControl size="small" sx={{ minWidth: 180 }}>
                        <InputLabel>Metric</InputLabel>
                        <Select
                          label="Metric"
                          value={m.metric_code}
                          onChange={(e) =>
                            updateMapping(idx, { metric_code: e.target.value })
                          }
                        >
                          {METRIC_CODES.map((mc) => (
                            <MenuItem key={mc} value={mc}>
                              {mc}
                            </MenuItem>
                          ))}
                        </Select>
                      </FormControl>
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        value={m.geography ?? ""}
                        onChange={(e) =>
                          updateMapping(idx, {
                            geography: e.target.value || null,
                          })
                        }
                        sx={{ width: 110 }}
                      />
                    </TableCell>
                    <TableCell>
                      <TextField
                        size="small"
                        value={m.bu_id ?? ""}
                        onChange={(e) =>
                          updateMapping(idx, { bu_id: e.target.value || null })
                        }
                        sx={{ width: 90 }}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton size="small" onClick={() => removeMapping(idx)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {mappings.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <Box py={3} textAlign="center" color="text.secondary">
                        Click <strong>Map</strong> next to a row on the left to start.
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </Stack>
      )}

      <Paper sx={{ p: 2 }}>
        <Stack direction="row" spacing={2} alignItems="center">
          <Button
            variant="contained"
            onClick={handleSaveAndDryRun}
            disabled={dryRunning || mappings.length === 0}
          >
            {dryRunning ? "Saving…" : editingId ? "Save & dry-run" : "Create & dry-run"}
          </Button>
          {dryRunError && <Alert severity="error">{dryRunError}</Alert>}
        </Stack>

        {dryRun && (
          <Box mt={2}>
            <Typography variant="subtitle2">Dry-run result</Typography>
            <Stack direction="row" spacing={2} mt={1}>
              <Chip label={`${dryRun.monthly_count} monthly rows`} />
              <Chip label={`${dryRun.bu_count} BU rows`} />
              <Chip label={`Latest: ${dryRun.period_year}-${String(dryRun.period_month).padStart(2, "0")}`} />
            </Stack>
            <Box mt={2}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Month</TableCell>
                    <TableCell>Geo</TableCell>
                    <TableCell align="right">Revenue</TableCell>
                    <TableCell align="right">COGS</TableCell>
                    <TableCell align="right">Gross margin</TableCell>
                    <TableCell align="right">EBITDA</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {dryRun.sample_monthly.map((r, i) => (
                    <TableRow key={i}>
                      <TableCell>{r.month_date}</TableCell>
                      <TableCell>{r.geography}</TableCell>
                      <TableCell align="right">{r.revenue_lacs ?? "—"}</TableCell>
                      <TableCell align="right">{r.cogs_lacs ?? "—"}</TableCell>
                      <TableCell align="right">{r.gross_margin_lacs ?? "—"}</TableCell>
                      <TableCell align="right">{r.ebitda_lacs ?? "—"}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Box>
            <Box mt={2}>
              <Button onClick={() => navigate("/mis/templates")} variant="outlined">
                Done
              </Button>
            </Box>
          </Box>
        )}
      </Paper>
    </Stack>
  );
}

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
