import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SearchIcon from "@mui/icons-material/Search";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogContentText from "@mui/material/DialogContentText";
import DialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";

import {
  useDeleteTemplate,
  useSetTemplateDefault,
  useTemplates,
} from "../../../api/misTemplates";

export default function MisTemplateListPage() {
  const navigate = useNavigate();
  const [companyFilter, setCompanyFilter] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  const { data, isLoading } = useTemplates(companyFilter || undefined);
  const setDefault = useSetTemplateDefault();
  const remove = useDeleteTemplate();

  function confirmDelete() {
    if (deleteTarget) {
      remove.mutate(deleteTarget.id);
      setDeleteTarget(null);
    }
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Box>
          <Typography variant="h4" component="h1">
            MIS Templates
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
            Manage Excel import row-mapping templates per company.
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate("/mis/templates/new")}
        >
          New template
        </Button>
      </Stack>

      <Paper sx={{ p: 2 }}>
        <TextField
          placeholder="Filter by company code…"
          size="small"
          value={companyFilter}
          onChange={(e) => setCompanyFilter(e.target.value)}
          sx={{ minWidth: 260 }}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
              </InputAdornment>
            ),
          }}
        />
      </Paper>

      <Paper>
        {isLoading ? (
          <Box display="flex" justifyContent="center" p={6}>
            <CircularProgress />
          </Box>
        ) : (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>#</TableCell>
                  <TableCell>Name</TableCell>
                  <TableCell>Company</TableCell>
                  <TableCell>Sheet Pattern</TableCell>
                  <TableCell align="center">Mappings</TableCell>
                  <TableCell align="center">Version</TableCell>
                  <TableCell align="center">Default</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data?.map((t) => (
                  <TableRow
                    key={t.id}
                    hover
                    onClick={() => navigate(`/mis/templates/${t.id}/edit`)}
                    sx={{ cursor: "pointer" }}
                  >
                    <TableCell sx={{ color: "text.disabled", fontSize: "0.75rem" }}>
                      {t.id}
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {t.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      {t.company_id ? (
                        <Chip
                          size="small"
                          label={t.company_id}
                          variant="outlined"
                          sx={{ fontFamily: "monospace", fontSize: "0.75rem" }}
                        />
                      ) : (
                        <Chip size="small" label="Global" color="primary" variant="outlined" />
                      )}
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
                          display: "inline-block",
                          maxWidth: 220,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {t.sheet_name_pattern ?? "—"}
                      </Box>
                    </TableCell>
                    <TableCell align="center">
                      <Chip size="small" label={t.row_mappings.length} />
                    </TableCell>
                    <TableCell align="center">
                      <Typography variant="caption" color="text.secondary">
                        v{t.version}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title={t.is_default ? "Default template" : "Set as default"}>
                        <span>
                          <IconButton
                            size="small"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!t.is_default) setDefault.mutate(t.id);
                            }}
                            disabled={t.is_default}
                          >
                            {t.is_default ? (
                              <StarIcon sx={{ fontSize: 18, color: "#D97706" }} />
                            ) : (
                              <StarBorderIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                            )}
                          </IconButton>
                        </span>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <Tooltip title="Delete template">
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteTarget({ id: t.id, name: t.name });
                          }}
                          sx={{ color: "text.disabled", "&:hover": { color: "error.main" } }}
                        >
                          <DeleteOutlineIcon fontSize="small" />
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                  </TableRow>
                ))}
                {data && data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Stack alignItems="center" spacing={1} py={5}>
                        <Typography color="text.secondary" variant="body2">
                          No templates found.
                        </Typography>
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<AddIcon />}
                          onClick={() => navigate("/mis/templates/new")}
                        >
                          Create first template
                        </Button>
                      </Stack>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

      {/* Delete confirmation dialog */}
      <Dialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle>Delete template?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete{" "}
            <strong>&ldquo;{deleteTarget?.name}&rdquo;</strong>? This action cannot be undone.
          </DialogContentText>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteTarget(null)} color="inherit">
            Cancel
          </Button>
          <Button
            onClick={confirmDelete}
            variant="contained"
            color="error"
            disableElevation
          >
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
