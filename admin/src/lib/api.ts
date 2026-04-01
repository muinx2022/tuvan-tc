import axios from "axios";
import type { InternalAxiosRequestConfig } from "axios";
import { clearAuthSession, getAccessToken, getRefreshToken, updateAccessSession } from "./auth-storage";

// Ưu tiên /api/v1 (cùng origin + Vite proxy → Django). Override bằng VITE_API_URL nếu cần.
export const apiUrl = import.meta.env.VITE_API_URL ?? "/api/v1";

export type ApiEnvelope<T> = {
  success: boolean;
  message: string;
  data: T;
};

export const apiClient = axios.create({
  baseURL: apiUrl,
});

let refreshPromise: Promise<string | null> | null = null;
let lastSessionSyncAt = 0;

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const parts = token.split(".");
    if (parts.length < 2) {
      return null;
    }
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64.padEnd(Math.ceil(base64.length / 4) * 4, "=");
    return JSON.parse(window.atob(padded)) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function isTokenExpiringSoon(token: string, skewSeconds = 60): boolean {
  const payload = decodeJwtPayload(token);
  const exp = payload?.exp;
  if (typeof exp !== "number") {
    return false;
  }
  const nowSeconds = Math.floor(Date.now() / 1000);
  return exp - nowSeconds <= skewSeconds;
}

function redirectToLoginForExpiredSession() {
  clearAuthSession();
  if (window.location.pathname !== "/login") {
    window.location.replace("/login?reason=session-expired");
  }
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return null;
  }
  if (!refreshPromise) {
    refreshPromise = axios
      .post<ApiEnvelope<{
        accessToken: string;
        refreshToken: string;
        userId: number;
        fullName: string;
        email: string;
        role: string;
        permissions?: string[];
      }>>(`${apiUrl}/auth/refresh`, {
        refreshToken,
      })
      .then((res) => {
        lastSessionSyncAt = Date.now();
        updateAccessSession(res.data.data.accessToken, res.data.data.refreshToken, JSON.stringify(res.data.data));
        return res.data.data.accessToken;
      })
      .catch((error: unknown) => {
        const status = axios.isAxiosError(error) ? error.response?.status : undefined;
        if (status === 400 || status === 401 || status === 403) {
          redirectToLoginForExpiredSession();
        }
        return null;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

export async function ensureFreshSession(force = false): Promise<string | null> {
  const refreshToken = getRefreshToken();
  const accessToken = getAccessToken();
  if (!refreshToken) {
    return accessToken;
  }

  const recentlySynced = Date.now() - lastSessionSyncAt < 60_000;
  const shouldRefresh =
    !accessToken ||
    isTokenExpiringSoon(accessToken, 5 * 60) ||
    (force && !recentlySynced);

  if (!shouldRefresh) {
    return accessToken;
  }

  const refreshedToken = await refreshAccessToken();
  if (refreshedToken) {
    return refreshedToken;
  }

  const latestAccessToken = getAccessToken();
  if (latestAccessToken && !isTokenExpiringSoon(latestAccessToken, 0) && !force) {
    return latestAccessToken;
  }
  return null;
}

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const token = await ensureFreshSession();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error.response?.status;
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const url = originalRequest?.url ?? "";

    if ((status === 401 || status === 403) && originalRequest && !originalRequest._retry && !url.includes("/auth/login") && !url.includes("/auth/refresh")) {
      originalRequest._retry = true;
      const nextAccessToken = await refreshAccessToken();
      if (nextAccessToken) {
        originalRequest.headers = originalRequest.headers ?? {};
        originalRequest.headers.Authorization = `Bearer ${nextAccessToken}`;
        return apiClient(originalRequest);
      }
    }

    if ((status === 401 || status === 403) && !getRefreshToken()) {
      redirectToLoginForExpiredSession();
    }

    return Promise.reject(error);
  },
);
