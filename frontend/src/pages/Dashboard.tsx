import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { useAuthStore } from "../stores/auth";

export default function Dashboard() {
  const user = useAuthStore((s) => s.user);

  return (
    <Paper elevation={1} sx={{ p: 4, maxWidth: 720 }}>
      <Stack spacing={2}>
        <Typography variant="h4" component="h1">
          Welcome{user ? `, ${user.full_name}` : ""}
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Use the sidebar to manage the portfolio. MIS, reminders, and
          analytics modules will land here in upcoming sprints.
        </Typography>
        {user && (
          <Typography variant="body2" color="text.secondary">
            Signed in as <strong>{user.email}</strong>
          </Typography>
        )}
      </Stack>
    </Paper>
  );
}
