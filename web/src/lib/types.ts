export type Role = "ROLE_USER" | "ROLE_AUTHENTICATED" | "ROLE_ADMIN";

export type ApiEnvelope<T> = {
  success: boolean;
  message: string;
  data: T;
};

export type AuthResponse = {
  accessToken: string;
  refreshToken: string;
  userId: number;
  fullName: string;
  email: string;
  role: Role;
  permissions: string[];
};

export type UserSummary = {
  id: number;
  fullName: string;
  email: string;
  role: Role;
};

export type Product = {
  id: number;
  ownerId: number;
  ownerName: string;
  name: string;
  description: string | null;
  price: number;
  createdAt: string;
  updatedAt: string;
};

export type PasswordResetResponse = {
  email: string;
  resetToken: string | null;
  expiresAt: string | null;
  tokenExposed: boolean;
};
