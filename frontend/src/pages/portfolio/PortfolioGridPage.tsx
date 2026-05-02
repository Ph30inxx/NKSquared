import { useCallback, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import type {
  CellValueChangedEvent,
  ColDef,
  GridOptions,
  GridReadyEvent,
  ValueFormatterParams,
} from "ag-grid-community";
import "ag-grid-community/styles/ag-grid.css";
import "ag-grid-community/styles/ag-theme-alpine.css";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Snackbar from "@mui/material/Snackbar";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import {
  ASSET_CLASSES,
  CompanyDetail,
  CompanyListItem,
  CompanyWritePayload,
  INVESTMENT_STATUSES,
  PORTFOLIO_STATUSES,
  PORTFOLIO_TYPES,
  updateCompany,
  useCompanies,
} from "../../api/companies";
import { moicColor } from "../../utils/format";

type GridRow = CompanyListItem;
type EditableField = keyof CompanyWritePayload;

interface ToastState {
  severity: "success" | "error" | "info";
  message: string;
}

function toNumberOrNull(value: unknown): number | null {
  if (value === "" || value == null) return null;
  const num = typeof value === "number" ? value : Number(value);
  return Number.isFinite(num) ? num : null;
}

function emptyToNull(value: unknown): unknown {
  return value === "" ? null : value;
}

const NUMBER_FMT = (p: ValueFormatterParams) => {
  if (p.value == null || p.value === "") return "—";
  const num = typeof p.value === "number" ? p.value : Number(p.value);
  return Number.isFinite(num) ? num.toFixed(2) : "—";
};

const ABS_NUMBER_FMT = (p: ValueFormatterParams) => {
  if (p.value == null || p.value === "") return "—";
  const num = typeof p.value === "number" ? p.value : Number(p.value);
  return Number.isFinite(num) ? Math.abs(num).toFixed(2) : "—";
};

const MOIC_FMT = (p: ValueFormatterParams) => {
  if (p.value == null || p.value === "") return "—";
  const num = typeof p.value === "number" ? p.value : Number(p.value);
  return Number.isFinite(num) ? `${num.toFixed(2)}x` : "—";
};

const IRR_FMT = (p: ValueFormatterParams) => {
  if (p.value == null || p.value === "") return "—";
  const num = typeof p.value === "number" ? p.value : Number(p.value);
  return Number.isFinite(num) ? `${(num * 100).toFixed(1)}%` : "—";
};

export default function PortfolioGridPage() {
  // Pull all active companies in one shot; AG Grid handles client-side pagination.
  const { data, isLoading, isError, refetch } = useCompanies({ limit: 1000 });
  const gridRef = useRef<AgGridReact<GridRow>>(null);
  const [toast, setToast] = useState<ToastState | null>(null);

  const columnDefs = useMemo<ColDef<GridRow>[]>(
    () => [
      {
        field: "id",
        headerName: "Code",
        editable: false,
        pinned: "left",
        width: 80,
        filter: "agNumberColumnFilter",
      },
      {
        field: "display_name",
        headerName: "Company",
        pinned: "left",
        editable: true,
        width: 220,
        valueGetter: (p) => p.data?.display_name || p.data?.company_name || "",
      },
      { field: "sector", headerName: "Sector", editable: true, width: 140 },
      { field: "sub_sector", headerName: "Sub-sector", editable: true, width: 160 },
      {
        field: "portfolio_type",
        headerName: "Vehicle",
        editable: true,
        width: 180,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: ["", ...PORTFOLIO_TYPES] },
        valueFormatter: (p) =>
          typeof p.value === "string" ? p.value.replace(/_/g, " ") : "—",
      },
      {
        field: "asset_class",
        headerName: "Asset class",
        editable: true,
        width: 160,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: ["", ...ASSET_CLASSES] },
        valueFormatter: (p) =>
          typeof p.value === "string" ? p.value.replace(/_/g, " ") : "—",
      },
      {
        field: "investment_status",
        headerName: "Status",
        editable: true,
        width: 170,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: ["", ...INVESTMENT_STATUSES] },
        valueFormatter: (p) =>
          typeof p.value === "string" ? p.value.replace(/_/g, " ") : "—",
      },
      {
        field: "portfolio_status",
        headerName: "P. status",
        editable: true,
        width: 130,
        cellEditor: "agSelectCellEditor",
        cellEditorParams: { values: ["", ...PORTFOLIO_STATUSES] },
      },
      { field: "country", headerName: "Country", editable: true, width: 120 },
      {
        field: "date_of_first_investment",
        headerName: "First invest",
        editable: true,
        width: 140,
        cellEditor: "agDateStringCellEditor",
      },
      {
        field: "currency",
        headerName: "Ccy",
        editable: true,
        width: 90,
      },
      {
        field: "investment_value_cr",
        headerName: "Invested (₹Cr)",
        editable: false,
        width: 140,
        type: "numericColumn",
        valueFormatter: ABS_NUMBER_FMT,
        filter: "agNumberColumnFilter",
      },
      {
        field: "current_value_cr",
        headerName: "Current (₹Cr)",
        editable: true,
        width: 140,
        type: "numericColumn",
        cellEditor: "agNumberCellEditor",
        valueFormatter: NUMBER_FMT,
        filter: "agNumberColumnFilter",
      },
      {
        field: "moic",
        headerName: "MOIC",
        editable: false,
        width: 100,
        type: "numericColumn",
        valueFormatter: MOIC_FMT,
        cellStyle: (p) => ({ color: moicColor(p.value) ?? "inherit" }),
        filter: "agNumberColumnFilter",
      },
      {
        field: "irr",
        headerName: "IRR",
        editable: false,
        width: 100,
        type: "numericColumn",
        valueFormatter: IRR_FMT,
        filter: "agNumberColumnFilter",
      },
      { field: "notes", headerName: "Notes", editable: true, width: 200 },
    ],
    [],
  );

  const gridOptions = useMemo<GridOptions<GridRow>>(
    () => ({
      // enableRangeSelection / enableFillHandle are AG Grid Enterprise — omitted on Community.
      // Single-cell Ctrl/⌘+C / Ctrl/⌘+V clipboard interop with Excel still works.
      copyHeadersToClipboard: true,
      undoRedoCellEditing: true,
      undoRedoCellEditingLimit: 50,
      rowSelection: "multiple",
      suppressRowClickSelection: true,
      pagination: true,
      paginationPageSize: 50,
      defaultColDef: { sortable: true, filter: true, resizable: true },
      animateRows: true,
      singleClickEdit: false, // double-click to edit, like Excel
      stopEditingWhenCellsLoseFocus: true,
    }),
    [],
  );

  const onCellValueChanged = useCallback(
    async (params: CellValueChangedEvent<GridRow>) => {
      const field = params.colDef.field as EditableField | undefined;
      if (!field || !params.data) return;
      if (params.newValue === params.oldValue) return;

      const id = params.data.id;
      const newValue = emptyToNull(params.newValue);
      // Cast numeric strings to numbers so the backend's Decimal validation accepts them.
      const numericFields = new Set<EditableField>(["current_value_cr"]);
      const sendValue = numericFields.has(field) ? toNumberOrNull(newValue) : newValue;

      try {
        const updated: CompanyDetail = await updateCompany(id, {
          [field]: sendValue,
        } as Partial<CompanyWritePayload>);
        // Reconcile the row with the server response so derived fields refresh.
        params.node.setData({
          ...params.data,
          ...updated,
        } as GridRow);
        setToast({ severity: "success", message: "Saved" });
      } catch (err: unknown) {
        const detail =
          (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
        let message = "Save failed";
        if (typeof detail === "string") message = detail;
        else if (Array.isArray(detail)) {
          const first = detail[0] as { msg?: string } | undefined;
          if (first?.msg) message = first.msg;
        }
        params.node.setDataValue(field, params.oldValue);
        setToast({ severity: "error", message });
      }
    },
    [],
  );

  const onGridReady = useCallback((p: GridReadyEvent<GridRow>) => {
    p.api.sizeColumnsToFit();
  }, []);

  return (
    <Stack spacing={2} sx={{ height: "100%" }}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" component="h1">
          Portfolio grid
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Double-click a cell to edit. Ctrl/⌘+C / Ctrl/⌘+V interop with Excel.
          Computed columns (Invested, MOIC, IRR) refresh after each save.
        </Typography>
      </Stack>

      {isError && <Alert severity="error">Could not load companies. <button onClick={() => refetch()}>Retry</button></Alert>}

      {isLoading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        <div
          className="ag-theme-alpine"
          style={
            {
              height: "calc(100vh - 200px)",
              width: "100%",
              minHeight: 480,
              // Alpine paints horizontal row borders by default but leaves columns
              // unseparated; these CSS vars draw vertical borders between every
              // body cell and put a divider line between every header cell so
              // the page reads as an actual spreadsheet.
              "--ag-cell-horizontal-border": "solid 1px var(--ag-border-color)",
              "--ag-header-column-separator-display": "block",
              "--ag-header-column-separator-color": "var(--ag-border-color)",
              "--ag-header-column-separator-width": "1px",
              "--ag-header-column-separator-height": "100%",
            } as React.CSSProperties
          }
        >
          <AgGridReact<GridRow>
            ref={gridRef}
            rowData={data?.items ?? []}
            columnDefs={columnDefs}
            gridOptions={gridOptions}
            getRowId={(p) => String(p.data.id)}
            onCellValueChanged={onCellValueChanged}
            onGridReady={onGridReady}
          />
        </div>
      )}

      <Snackbar
        open={toast != null}
        autoHideDuration={toast?.severity === "error" ? 6000 : 2000}
        onClose={() => setToast(null)}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        {toast ? (
          <Alert
            severity={toast.severity}
            variant="filled"
            onClose={() => setToast(null)}
            sx={{ width: "100%" }}
          >
            {toast.message}
          </Alert>
        ) : undefined}
      </Snackbar>
    </Stack>
  );
}
