import { create } from "zustand";
import { persist } from "zustand/middleware";

export type UserRole = "ADMIN" | "ANALYST" | "VIEWER" | "COMPANY_USER";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  company_id: number | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: AuthUser | null;
  setTokens: (accessToken: string, refreshToken: string) => void;
  setUser: (user: AuthUser | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setUser: (user) => set({ user }),
      logout: () => set({ accessToken: null, refreshToken: null, user: null }),
    }),
    {
      name: "nksquared.auth",
      // Persist tokens only — user object is rehydrated from /auth/me on boot.
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    },
  ),
);
