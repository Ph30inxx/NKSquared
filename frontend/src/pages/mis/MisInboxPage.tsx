import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import RuleIcon from "@mui/icons-material/Rule";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
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
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" component="h1">
          MIS Inbox
        </Typography>
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
            label="Company code"
            size="small"
            value={companyFilter}
            onChange={(e) => {
              setCompanyFilter(e.target.value);
              setPage(0);
            }}
            placeholder="company_01"
            sx={{ minWidth: 200 }}
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
                      <TableCell>{s.id}</TableCell>
                      <TableCell>{s.company_id}</TableCell>
                      <TableCell>{periodLabel(s.period_year, s.period_month)}</TableCell>
                      <TableCell>{s.fiscal_year}</TableCell>
                      <TableCell>
                        <Chip
                          label={s.status}
                          color={STATUS_COLOR[s.status as MisSubmissionStatus] ?? "default"}
                          size="small"
                        />
                      </TableCell>
                      <TableCell>{s.source_file_name ?? "—"}</TableCell>
                      <TableCell>{s.uploaded_at ? formatDate(s.uploaded_at) : "—"}</TableCell>
                      <TableCell>{s.reviewed_at ? formatDate(s.reviewed_at) : "—"}</TableCell>
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
