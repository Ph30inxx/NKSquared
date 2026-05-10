import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import RuleIcon from "@mui/icons-material/Rule";
import SearchIcon from "@mui/icons-material/Search";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TablePagination from "@mui/material/TablePagination";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";

import {
  MIS_STATUS_FILTERS,
  MisSubmissionStatus,
  useMisSubmissions,
} from "../../api/mis";
import { formatDate } from "../../utils/format";
import BulkExportDialog from "./BulkExportDialog";
import MisUploadDialog from "./MisUploadDialog";

const STATUS_COLOR: Record<
  MisSubmissionStatus,
  "default" | "warning" | "info" | "success" | "error"
> = {
  Pending: "default",
  Submitted: "info",
  "Under Review": "warning",
  Approved: "success",
  Rejected: "error",
  "Resubmission Required": "warning",
};

function periodLabel(year: number, month: number): string {
  const d = new Date(year, month - 1, 1);
  return d.toLocaleDateString("en-IN", { year: "numeric", month: "short" });
}

export default function MisInboxPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [statusFilter, setStatusFilter] = useState<MisSubmissionStatus | "All">("All");
  const [companyFilter, setCompanyFilter] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);

  const { data, isLoading } = useMisSubmissions({
    limit: rowsPerPage,
    offset: page * rowsPerPage,
    status: statusFilter === "All" ? undefined : statusFilter,
    company_id: companyFilter || undefined,
  });

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Typography variant="h4" component="h1">
            MIS Inbox
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Review and approve monthly information submissions.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<RuleIcon />}
            onClick={() => navigate("/mis/templates")}
          >
            Templates
          </Button>
          <Button
            variant="outlined"
            startIcon={<FileDownloadIcon />}
            onClick={() => setExportOpen(true)}
          >
            Bulk export
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setUploadOpen(true)}
          >
            New submission
          </Button>
        </Stack>
      </Stack>

      <Paper sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2} alignItems="center">
          <ToggleButtonGroup
            value={statusFilter}
            exclusive
            onChange={(_, v) => {
              if (v) {
                setStatusFilter(v);
                setPage(0);
              }
            }}
            size="small"
          >
            {MIS_STATUS_FILTERS.map((s) => (
              <ToggleButton key={s} value={s}>
                {s}
              </ToggleButton>
            ))}
          </ToggleButtonGroup>
          <TextField
            placeholder="Filter by company code…"
            size="small"
            value={companyFilter}
            onChange={(e) => {
              setCompanyFilter(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 220 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                </InputAdornment>
              ),
            }}
          />
        </Stack>
      </Paper>

      <Paper>
        {isLoading ? (
          <Box display="flex" justifyContent="center" p={4}>
            <CircularProgress />
          </Box>
        ) : (
          <>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>#</TableCell>
                    <TableCell>Company</TableCell>
                    <TableCell>Period</TableCell>
                    <TableCell>FY</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell>File</TableCell>
                    <TableCell>Uploaded</TableCell>
                    <TableCell>Reviewed</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data?.items.map((s) => (
                    <TableRow
                      hover
                      key={s.id}
                      onClick={() => navigate(`/mis/${s.id}`)}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell sx={{ color: "text.disabled", fontSize: "0.75rem" }}>
                        #{s.id}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {s.company_id}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2">
                          {periodLabel(s.period_year, s.period_month)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {s.fiscal_year}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={s.status}
                          color={STATUS_COLOR[s.status as MisSubmissionStatus] ?? "default"}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>
                        {s.source_file_name ? (
                          <Tooltip title={s.source_file_name}>
                            <Typography
                              variant="caption"
                              sx={{
                                maxWidth: 160,
                                display: "block",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                color: "text.secondary",
                              }}
                            >
                              {s.source_file_name}
                            </Typography>
                          </Tooltip>
                        ) : (
                          <Typography variant="caption" color="text.disabled">—</Typography>
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {s.uploaded_at ? formatDate(s.uploaded_at) : "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {s.reviewed_at ? formatDate(s.reviewed_at) : "—"}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {data && data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8}>
                        <Box py={4} textAlign="center" color="text.secondary">
                          No submissions match. Click <strong>New submission</strong> above.
                        </Box>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              component="div"
              count={data?.total ?? 0}
              page={page}
              onPageChange={(_, p) => setPage(p)}
              rowsPerPage={rowsPerPage}
              onRowsPerPageChange={(e) => {
                setRowsPerPage(Number(e.target.value));
                setPage(0);
              }}
              rowsPerPageOptions={[10, 25, 50, 100]}
            />
          </>
        )}
      </Paper>

      <MisUploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} />
      <BulkExportDialog open={exportOpen} onClose={() => setExportOpen(false)} />
    </Stack>
  );
}
