import { api } from "./client";
import type { AuthUser } from "../stores/auth";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/login", { email, password });
  return data;
}

export async function getMe(): Promise<AuthUser> {
  const { data } = await api.get<AuthUser>("/auth/me");
  return data;
}

export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/refresh", {
    refresh_token: refreshToken,
  });
  return data;
}
