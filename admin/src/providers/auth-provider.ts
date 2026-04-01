import type { AuthProvider } from "@refinedev/core";
import { apiClient, ensureFreshSession } from "../lib/api";
import type { ApiEnvelope } from "../lib/api";
import { clearAuthSession, getStoredUser, setAuthSession } from "../lib/auth-storage";

type AuthResponse = {
  accessToken: string;
  refreshToken: string;
  userId: number;
  fullName: string;
  email: string;
  role: string;
  permissions?: string[];
};

export const authProvider: AuthProvider = {
  login: async ({ email, password, rememberMe }) => {
    try {
      const res = await apiClient.post<ApiEnvelope<AuthResponse>>("/auth/login", {
        email,
        password,
      });

      const role = res.data.data.role;
      const permissions = res.data.data.permissions ?? [];
      const canAccessAdmin = role === "ROLE_ADMIN" || permissions.includes("admin.portal.access");
      if (!canAccessAdmin) {
        const message =
          role === "ROLE_AUTHENTICATED" || role === "ROLE_USER"
            ? "Tai khoan nay chi dung cho web, khong co quyen vao admin"
            : "Tai khoan khong co quyen admin portal";
        return {
          success: false,
          error: { name: "Forbidden", message },
        };
      }

      setAuthSession({
        accessToken: res.data.data.accessToken,
        refreshToken: res.data.data.refreshToken,
        user: JSON.stringify(res.data.data),
        remember: Boolean(rememberMe),
      });
      return {
        success: true,
        redirectTo: "/dashboard",
      };
    } catch (e) {
      return {
        success: false,
        error: { name: "LoginError", message: (e as Error).message },
      };
    }
  },
  logout: async () => {
    clearAuthSession();
    return { success: true, redirectTo: "/login" };
  },
  onError: async (error) => {
    const status = (error as { statusCode?: number })?.statusCode;
    if (status === 401 || status === 403) {
      clearAuthSession();
      return { error: { name: "Unauthorized", message: "Unauthorized" }, logout: true };
    }
    return { error };
  },
  check: async () => {
    const token = await ensureFreshSession(true);
    if (token) {
      return { authenticated: true };
    }
    return {
      authenticated: false,
      logout: true,
      redirectTo: "/login",
      error: { name: "Unauthorized", message: "Not authenticated" },
    };
  },
  getIdentity: async () => {
    const raw = getStoredUser();
    if (!raw) {
      return null;
    }
    const user = JSON.parse(raw) as AuthResponse;
    return {
      id: user.userId,
      name: user.fullName,
      avatar: undefined,
    };
  },
  getPermissions: async () => {
    const raw = getStoredUser();
    if (!raw) {
      return [];
    }
    const user = JSON.parse(raw) as AuthResponse;
    return user.permissions ?? [user.role];
  },
};
