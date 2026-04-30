import { useQuery } from "@tanstack/react-query";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Container from "@mui/material/Container";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";

import { api } from "./api/client";

interface HealthResponse {
  status: string;
  service: string;
}

function useApiHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: async () => (await api.get<HealthResponse>("/health")).data,
    refetchInterval: 10_000,
    retry: 1,
  });
}

export default function App() {
  const health = useApiHealth();

  const apiState = health.isLoading
    ? { label: "API: checking…", color: "default" as const }
    : health.isError
      ? { label: "API: unreachable", color: "error" as const }
      : { label: `API: ${health.data?.status ?? "unknown"}`, color: "success" as const };

  return (
    <Container maxWidth="md" sx={{ py: 8 }}>
      <Stack spacing={3}>
        <Typography variant="h3" component="h1">
          NKSquared
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Investment Intelligence Platform — scaffolding only. Implementation
          begins in Sprint 1 of the plan.
        </Typography>
        <Box>
          <Chip label={apiState.label} color={apiState.color} />
        </Box>
      </Stack>
    </Container>
  );
}
