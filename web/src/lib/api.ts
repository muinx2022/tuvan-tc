import axios, { AxiosError } from "axios";
import { clearAuth, getAccessToken, getRefreshToken, saveAuth } from "./auth";
import type {
  ApiEnvelope,
  AuthResponse,
  PasswordResetResponse,
  Product,
  UserSummary,
} from "./types";

function resolveApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8080/api/v1`;
  }
  return "http://localhost:8080/api/v1";
}

const api = axios.create({
  baseURL: resolveApiBaseUrl(),
});

api.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? getAccessToken() : null;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiEnvelope<unknown>>) => {
    if (error.response?.status !== 401 || !error.config || typeof window === "undefined") {
      return Promise.reject(error);
    }

    const refreshToken = getRefreshToken();
    if (!refreshToken) {
      clearAuth();
      return Promise.reject(error);
    }

    try {
      const refreshRes = await axios.post<ApiEnvelope<AuthResponse>>(
        `${resolveApiBaseUrl()}/auth/refresh`,
        { refreshToken },
      );
      saveAuth(refreshRes.data.data);
      error.config.headers.Authorization = `Bearer ${refreshRes.data.data.accessToken}`;
      return api.request(error.config);
    } catch (refreshError) {
      clearAuth();
      return Promise.reject(refreshError);
    }
  },
);

function extractError(error: unknown): string {
  if (axios.isAxiosError<ApiEnvelope<unknown>>(error)) {
    return error.response?.data?.message ?? "Unexpected API error";
  }
  return "Unexpected API error";
}

export async function register(payload: {
  fullName: string;
  email: string;
  password: string;
}): Promise<AuthResponse> {
  try {
    const res = await api.post<ApiEnvelope<AuthResponse>>("/auth/register", payload);
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function login(payload: {
  email: string;
  password: string;
}): Promise<AuthResponse> {
  try {
    const res = await api.post<ApiEnvelope<AuthResponse>>("/auth/login", payload);
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function loginWithGoogle(idToken: string): Promise<AuthResponse> {
  try {
    const res = await api.post<ApiEnvelope<AuthResponse>>("/auth/google", { idToken });
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function getGoogleOauthPublicConfig(): Promise<{ enabled: boolean; clientId: string }> {
  try {
    const res = await api.get<ApiEnvelope<{ enabled: boolean; clientId: string }>>("/public/settings/google-oauth");
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function forgotPassword(email: string): Promise<PasswordResetResponse> {
  try {
    const res = await api.post<ApiEnvelope<PasswordResetResponse>>("/auth/forgot-password", {
      email,
    });
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function resetPassword(token: string, password: string): Promise<void> {
  try {
    await api.post("/auth/reset-password", { token, password });
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function me(): Promise<UserSummary> {
  try {
    const res = await api.get<ApiEnvelope<UserSummary>>("/users/me");
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function listProducts(): Promise<Product[]> {
  try {
    const res = await api.get<ApiEnvelope<Product[]>>("/products");
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function createProduct(payload: {
  name: string;
  description: string;
  price: number;
}): Promise<Product> {
  try {
    const res = await api.post<ApiEnvelope<Product>>("/products", payload);
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function updateProduct(
  id: number,
  payload: { name: string; description: string; price: number },
): Promise<Product> {
  try {
    const res = await api.put<ApiEnvelope<Product>>(`/products/${id}`, payload);
    return res.data.data;
  } catch (error) {
    throw new Error(extractError(error));
  }
}

export async function deleteProduct(id: number): Promise<void> {
  try {
    await api.delete(`/products/${id}`);
  } catch (error) {
    throw new Error(extractError(error));
  }
}
