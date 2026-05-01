import { useEffect, useState, type ReactNode } from "react";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";

import { getMe } from "../api/auth";
import { useAuthStore } from "../stores/auth";

interface AppBootstrapProps {
  children: ReactNode;
}

/**
 * On mount, if a token was rehydrated from localStorage but we don't have a
 * user object yet, fetch /auth/me. Renders a spinner until that resolves.
 */
export default function AppBootstrap({ children }: AppBootstrapProps) {
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const [loading, setLoading] = useState(Boolean(accessToken) && !user);

  useEffect(() => {
    if (!accessToken || user) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    getMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) logout();
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [accessToken, user, setUser, logout]);

  if (loading) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" minHeight="100vh">
        <CircularProgress />
      </Box>
    );
  }
  return <>{children}</>;
}
