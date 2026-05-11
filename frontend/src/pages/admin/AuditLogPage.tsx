import { useMemo, useState } from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import FormControl from "@mui/material/FormControl";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Paper from "@mui/material/Paper";
import Select from "@mui/material/Select";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TablePagination from "@mui/material/TablePagination";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

import { ACTIONS, ENTITY_TYPES, useAuditLog } from "../../api/audit";

const ACTION_COLOR: Record<string, "default" | "info" | "success" | "warning" | "error"> = {
  CREATE: "success",
  UPDATE: "info",
  DELETE: "error",
  APPROVE: "success",
  REJECT: "warning",
  UPLOAD: "info",
  MARK_CURRENT: "info",
};

function fmtTs(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function truncate(s: string | null, n = 60): string {
  if (!s) return "";
  return s.length > n ? `${s.slice(0, n)}…` : s;
}

export default function AuditLogPage() {
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [entityType, setEntityType] = useState<string>("All");
  const [action, setAction] = useState<string>("All");
  const [entityIdStr, setEntityIdStr] = useState("");
  const [userIdStr, setUserIdStr] = useState("");

  const params = useMemo(() => {
    const p: Record<string, unknown> = {
      limit: rowsPerPage,
      offset: page * rowsPerPage,
    };
    if (entityType !== "All") p.entity_type = entityType;
    if (action !== "All") p.action = action;
    const eid = Number(entityIdStr);
    if (entityIdStr && !Number.isNaN(eid)) p.entity_id = eid;
    const uid = Number(userIdStr);
    if (userIdStr && !Number.isNaN(uid)) p.user_id = uid;
    return p;
  }, [page, rowsPerPage, entityType, action, entityIdStr, userIdStr]);

  const { data, isLoading } = useAuditLog(params);

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4" component="h1">
          Audit Log
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
          Complete trail of all system actions and data changes.
        </Typography>
      </Box>

      <Paper sx={{ p: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Entity type</InputLabel>
            <Select
              label="Entity type"
              value={entityType}
              onChange={(e) => {
                setEntityType(e.target.value);
                setPage(0);
              }}
            >
              <MenuItem value="All">All</MenuItem>
              {ENTITY_TYPES.map((e) => (
                <MenuItem key={e} value={e}>
                  {e}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl size="small" sx={{ minWidth: 160 }}>
            <InputLabel>Action</InputLabel>
            <Select
              label="Action"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(0);
              }}
            >
              <MenuItem value="All">All</MenuItem>
              {ACTIONS.map((a) => (
                <MenuItem key={a} value={a}>
                  {a}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <TextField
            label="Entity ID"
            size="small"
            value={entityIdStr}
            onChange={(e) => {
              setEntityIdStr(e.target.value);
              setPage(0);
            }}
            sx={{ width: 130 }}
          />
          <TextField
            label="User ID"
            size="small"
            value={userIdStr}
            onChange={(e) => {
              setUserIdStr(e.target.value);
              setPage(0);
            }}
            sx={{ width: 130 }}
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
                    <TableCell>When</TableCell>
                    <TableCell>User</TableCell>
                    <TableCell>Action</TableCell>
                    <TableCell>Entity</TableCell>
                    <TableCell>Field</TableCell>
                    <TableCell>Old → New</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data?.items.map((row) => (
                    <TableRow key={row.id} hover>
                      <TableCell>
                        <Typography variant="caption" sx={{ whiteSpace: "nowrap" }}>
                          {fmtTs(row.occurred_at)}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption">
                          {row.user_email ?? (row.user_id != null ? `#${row.user_id}` : "—")}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={row.action}
                          size="small"
                          color={ACTION_COLOR[row.action] ?? "default"}
                        />
                      </TableCell>
                      <TableCell>
                        <Box
                          component="code"
                          sx={{
                            fontSize: "0.75rem",
                            bgcolor: "action.hover",
                            px: 0.75,
                            py: 0.25,
                            borderRadius: 1,
                          }}
                        >
                          {row.entity_type}#{row.entity_id}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="caption" color="text.secondary">
                          {row.field_name ?? "—"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Tooltip
                          title={`OLD: ${row.old_value ?? "∅"} → NEW: ${row.new_value ?? "∅"}`}
                        >
                          <Box sx={{ fontSize: "0.8125rem" }}>
                            <Box
                              component="span"
                              sx={{ color: "text.disabled", textDecoration: "line-through" }}
                            >
                              {truncate(row.old_value)}
                            </Box>
                            {row.old_value && row.new_value && (
                              <Box component="span" sx={{ color: "text.disabled", mx: 0.5 }}>→</Box>
                            )}
                            <Box component="span" sx={{ color: "text.primary" }}>
                              {truncate(row.new_value)}
                            </Box>
                          </Box>
                        </Tooltip>
                      </TableCell>
                    </TableRow>
                  ))}
                  {data && data.items.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={6}>
                        <Box py={4} textAlign="center" color="text.secondary">
                          No audit entries match the current filters.
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
              rowsPerPageOptions={[25, 50, 100, 200]}
            />
          </>
        )}
      </Paper>
    </Stack>
  );
}
