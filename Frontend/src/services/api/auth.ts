/** Accounts module: /api/auth/ */
import type { Tokens, User } from "@/types/api";
import { api } from "./client";

export interface RegisterPayload {
  full_name: string;
  username: string;
  email: string;
  password: string;
  confirm_password: string;
  date_of_birth: string;
  phone_number: string;
  country: string;
}

export const authApi = {
  register: (body: RegisterPayload) =>
    api.post<{ user: User; email_verification_required: boolean; otp_expires_in_minutes: number }>("/auth/register/", body, { skipAuth: true }),
  verifyEmail: (email: string, otp: string) =>
    api.post<{ email_verified: boolean }>("/auth/verify-email/", { email, otp }, { skipAuth: true }),
  resendOtp: (email: string) =>
    api.post<{ otp_expires_in_minutes: number }>("/auth/resend-otp/", { email }, { skipAuth: true }),
  login: (email: string, password: string) =>
    api.post<{ user: User; tokens: Tokens }>("/auth/login/", { email, password }, { skipAuth: true }),
  logout: (refresh: string) => api.post<Record<string, never>>("/auth/logout/", { refresh }),
  forgotPassword: (email: string) =>
    api.post<{ otp_expires_in_minutes: number }>("/auth/forgot-password/", { email }, { skipAuth: true }),
  verifyResetOtp: (email: string, otp: string) =>
    api.post<{ reset_token: string; expires_in_minutes: number }>("/auth/verify-reset-otp/", { email, otp }, { skipAuth: true }),
  resetPassword: (token: string, new_password: string, confirm_password: string) =>
    api.post<Record<string, never>>("/auth/reset-password/", { token, new_password, confirm_password }, { skipAuth: true }),
  changePassword: (current_password: string, new_password: string, confirm_password: string) =>
    api.post<{ tokens: Tokens }>("/auth/change-password/", { current_password, new_password, confirm_password }),
  me: () => api.get<{ user: User }>("/auth/me/"),
  updateMe: (body: Partial<Pick<User, "full_name" | "username" | "email" | "phone_number" | "country" | "date_of_birth">> & { current_password?: string }) =>
    api.patch<{ user: User; email_changed?: boolean }>("/auth/me/", body),
};
