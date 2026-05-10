import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import FileDownloadIcon from "@mui/icons-material/FileDownload";
import SearchIcon from "@mui/icons-material/Search";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import InputAdornment from "@mui/material/InputAdornment";
import MenuItem from "@mui/material/MenuItem";
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
import Typography from "@mui/material/Typography";

import {
  INVESTMENT_STATUSES,
  PORTFOLIO_TYPES,
  useCompanies,
} from "../../api/companies";
import { downloadPortfolioXlsx } from "../../api/exports";
import { formatCr, formatMoic, moicColor } from "../../utils/format";
import CompanyFormDialog from "./CompanyFormDialog";

export default function PortfolioListPage() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(25);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [investmentStatus, setInvestmentStatus] = useState("");
  const [portfolioType, setPortfolioType] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await downloadPortfolioXlsx();
    } finally {
      setExporting(false);
    }
  }

  const { data, isLoading, isError, error } = useCompanies({
    limit: rowsPerPage,
    offset: page * rowsPerPage,
    q: q || undefined,
    sector: sector || undefined,
    investment_status: investmentStatus || undefined,
    portfolio_type: portfolioType || undefined,
  });

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="flex-start">
        <Box>
          <Typography variant="h4" component="h1">
            Portfolio
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Browse and manage all portfolio companies.
          </Typography>
        </Box>
        <Stack direction="row" spacing={1}>
          <Button
            variant="outlined"
            startIcon={<FileDownloadIcon />}
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? "Exporting…" : "Export to Excel"}
          </Button>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setCreateOpen(true)}
          >
            New company
          </Button>
        </Stack>
      </Stack>

      <Paper sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
          <TextField
            placeholder="Search company name…"
            size="small"
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(0);
            }}
            fullWidth
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                </InputAdornment>
              ),
            }}
          />
          <TextField
            label="Sector"
            size="small"
            value={sector}
            onChange={(e) => {
              setSector(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 160 }}
          />
          <TextField
            label="Status"
            size="small"
            select
            value={investmentStatus}
            onChange={(e) => {
              setInvestmentStatus(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="">Any status</MenuItem>
            {INVESTMENT_STATUSES.map((s) => (
              <MenuItem key={s} value={s}>
                {s.replace(/_/g, " ")}
              </MenuItem>
            ))}
          </TextField>
          <TextField
            label="Vehicle"
            size="small"
            select
            value={portfolioType}
            onChange={(e) => {
              setPortfolioType(e.target.value);
              setPage(0);
            }}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">Any vehicle</MenuItem>
            {PORTFOLIO_TYPES.map((t) => (
              <MenuItem key={t} value={t}>
                {t.replace(/_/g, " ")}
              </MenuItem>
            ))}
          </TextField>
        </Stack>
      </Paper>

      <Paper>
        {isError && (
          <Alert severity="error" sx={{ m: 2 }}>
            {(error as Error).message}
          </Alert>
        )}
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
                    <TableCell>Company</TableCell>
                    <TableCell>Sector</TableCell>
                    <TableCell>Vehicle</TableCell>
                    <TableCell>Status</TableCell>
                    <TableCell align="right">Invested (₹Cr)</TableCell>
                    <TableCell align="right">Current (₹Cr)</TableCell>
                    <TableCell align="right">MOIC</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data?.items.map((c) => (
                    <TableRow
                      hover
                      key={c.id}
                      onClick={() => navigate(`/portfolio/${c.id}`)}
                      sx={{ cursor: "pointer" }}
                    >
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {c.display_name || c.company_name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {c.sector ?? "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {c.portfolio_type ? (
                          <Chip
                            label={c.portfolio_type.replace(/_/g, " ")}
                            size="small"
                            variant="outlined"
                            sx={{ fontSize: "0.7rem" }}
                          />
                        ) : "—"}
                      </TableCell>
                      <TableCell>
                        {c.investment_status ? (
                          <Chip
                            label={c.investment_status.replace(/_/g, " ")}
                            size="small"
                            color={c.investment_status === "ACTIVE" ? "success" : "default"}
                            variant={c.investment_status === "ACTIVE" ? "filled" : "outlined"}
                            sx={{ fontSize: "0.7rem" }}
                          />
                        ) : "—"}
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontFamily="monospace">
                          {formatCr(
                            c.investment_value_cr ? Math.abs(Number(c.investment_value_cr)) : null,
                          )}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontFamily="monospace">
                          {formatCr(c.current_value_cr)}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Typography
                          variant="body2"
                          fontWeight={600}
                          fontFamily="monospace"
                          sx={{ color: moicColor(c.moic) }}
                        >
                          {formatMoic(c.moic)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                  {data && data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={7}>
                        <Stack alignItems="center" spacing={1} py={5}>
                          <Typography variant="body2" color="text.secondary">
                            No companies match your filters.
                          </Typography>
                          <Button
                            size="small"
                            variant="outlined"
                            startIcon={<AddIcon />}
                            onClick={() => setCreateOpen(true)}
                          >
                            Add first company
                          </Button>
                        </Stack>
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

      <CompanyFormDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={(c) => {
          setCreateOpen(false);
          navigate(`/portfolio/${c.id}`);
        }}
      />
    </Stack>
  );
}
