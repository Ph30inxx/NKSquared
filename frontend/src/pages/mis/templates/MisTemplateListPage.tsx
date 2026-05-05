import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AddIcon from "@mui/icons-material/Add";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import DeleteIcon from "@mui/icons-material/Delete";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import IconButton from "@mui/material/IconButton";
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
  const { data, isLoading } = useTemplates(companyFilter || undefined);
  const setDefault = useSetTemplateDefault();
  const remove = useDeleteTemplate();

  return (
    <Stack spacing={3}>
      <Stack direction="row" justifyContent="space-between" alignItems="center">
        <Typography variant="h4" component="h1">
          MIS Templates
        </Typography>
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
          label="Company code"
          size="small"
          value={companyFilter}
          onChange={(e) => setCompanyFilter(e.target.value)}
          placeholder="company_01"
          sx={{ minWidth: 240 }}
        />
      </Paper>

      <Paper>
        {isLoading ? (
          <Box display="flex" justifyContent="center" p={4}>
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
                  <TableCell>Sheet pattern</TableCell>
                  <TableCell>Mappings</TableCell>
                  <TableCell>Version</TableCell>
                  <TableCell>Default</TableCell>
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
                    <TableCell>{t.id}</TableCell>
                    <TableCell>{t.name}</TableCell>
                    <TableCell>
                      {t.company_id ?? <Chip size="small" label="Global" />}
                    </TableCell>
                    <TableCell>
                      <code>{t.sheet_name_pattern ?? "—"}</code>
                    </TableCell>
                    <TableCell>{t.row_mappings.length}</TableCell>
                    <TableCell>v{t.version}</TableCell>
                    <TableCell>
                      <Tooltip title={t.is_default ? "Default for company" : "Set as default"}>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (!t.is_default) setDefault.mutate(t.id);
                          }}
                        >
                          {t.is_default ? <StarIcon color="warning" /> : <StarBorderIcon />}
                        </IconButton>
                      </Tooltip>
                    </TableCell>
                    <TableCell align="right">
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          if (
                            window.confirm(`Delete template "${t.name}"?`)
                          ) {
                            remove.mutate(t.id);
                          }
                        }}
                      >
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
                {data && data.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Box py={4} textAlign="center" color="text.secondary">
                        No templates yet. Click <strong>New template</strong> to map a company's
                        Excel layout.
                      </Box>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Stack>
  );
}
