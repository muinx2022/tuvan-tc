export const TOKEN_KEY = "admin_access_token";
export const REFRESH_KEY = "admin_refresh_token";
export const USER_KEY = "admin_user";
export const REMEMBER_KEY = "admin_remember_me";

type StoredSession = {
  accessToken: string;
  refreshToken: string;
  user: string;
  remember: boolean;
};

function getActiveStorage(remember: boolean) {
  return remember ? localStorage : sessionStorage;
}

export function getRememberMe(): boolean {
  return localStorage.getItem(REMEMBER_KEY) === "true";
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY) ?? sessionStorage.getItem(TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY) ?? sessionStorage.getItem(REFRESH_KEY);
}

export function getStoredUser(): string | null {
  return localStorage.getItem(USER_KEY) ?? sessionStorage.getItem(USER_KEY);
}

export function setAuthSession(session: StoredSession) {
  clearAuthSession();
  const storage = getActiveStorage(session.remember);
  storage.setItem(TOKEN_KEY, session.accessToken);
  storage.setItem(REFRESH_KEY, session.refreshToken);
  storage.setItem(USER_KEY, session.user);
  localStorage.setItem(REMEMBER_KEY, String(session.remember));
}

export function updateAccessSession(accessToken: string, refreshToken: string, user?: string | null) {
  const remember = getRememberMe();
  const storage = getActiveStorage(remember);
  storage.setItem(TOKEN_KEY, accessToken);
  storage.setItem(REFRESH_KEY, refreshToken);
  if (user != null) {
    storage.setItem(USER_KEY, user);
  }
}

export function clearAuthSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(REMEMBER_KEY);
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  sessionStorage.removeItem(USER_KEY);
}
