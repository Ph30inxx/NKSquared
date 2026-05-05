import { useState } from "react";
import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Dialog from "@mui/material/Dialog";
import DialogActions from "@mui/material/DialogActions";
import DialogContent from "@mui/material/DialogContent";
import DialogTitle from "@mui/material/DialogTitle";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";

import { downloadBulkMisXlsx } from "../../api/exports";

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function BulkExportDialog({ open, onClose }: Props) {
  const [input, setInput] = useState("");
  const [chips, setChips] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleAdd(): void {
    const tokens = input
      .split(/[\s,]+/)
      .map((t) => t.trim())
      .filter(Boolean);
    if (!tokens.length) return;
    const next = Array.from(new Set([...chips, ...tokens]));
    setChips(next);
    setInput("");
  }

  function handleRemove(c: string): void {
    setChips(chips.filter((x) => x !== c));
  }

  async function handleDownload(): Promise<void> {
    if (chips.length === 0) {
      setError("Add at least one company code");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      await downloadBulkMisXlsx(chips);
      handleClose();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Download failed";
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  function handleClose(): void {
    setInput("");
    setChips([]);
    setError(null);
    setBusy(false);
    onClose();
  }

  return (
    <Dialog open={open} onClose={handleClose} fullWidth maxWidth="sm">
      <DialogTitle>Bulk MIS export</DialogTitle>
      <DialogContent>
        <Stack spacing={2} mt={1}>
          <TextField
            label="Add company codes (space- or comma-separated)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                handleAdd();
              }
            }}
            placeholder="company_01 company_02 company_03"
            fullWidth
            size="small"
          />
          <Box>
            <Button onClick={handleAdd} size="small" disabled={!input.trim()}>
              Add
            </Button>
          </Box>
          <Box display="flex" gap={1} flexWrap="wrap">
            {chips.map((c) => (
              <Chip key={c} label={c} onDelete={() => handleRemove(c)} />
            ))}
            {chips.length === 0 && (
              <Box color="text.secondary" fontSize="0.85rem">
                No companies queued — add codes above.
              </Box>
            )}
          </Box>
          {error && <Alert severity="error">{error}</Alert>}
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Cancel</Button>
        <Button variant="contained" onClick={handleDownload} disabled={busy}>
          {busy ? "Building workbook…" : `Download (${chips.length})`}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
