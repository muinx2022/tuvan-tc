import type { AuthResponse } from "./types";

const TOKEN_KEY = "mvp_access_token";
const REFRESH_KEY = "mvp_refresh_token";
const USER_KEY = "mvp_user";

export function saveAuth(auth: AuthResponse): void {
  localStorage.setItem(TOKEN_KEY, auth.accessToken);
  localStorage.setItem(REFRESH_KEY, auth.refreshToken);
  localStorage.setItem(USER_KEY, JSON.stringify(auth));
  document.cookie = `access_token=${auth.accessToken}; path=/; max-age=86400`;
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  document.cookie = "access_token=; path=/; max-age=0";
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function getUser(): AuthResponse | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) {
    return null;
  }
  return JSON.parse(raw) as AuthResponse;
}
