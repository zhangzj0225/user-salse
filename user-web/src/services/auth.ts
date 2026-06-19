import { request } from "./api";

export interface SendCodeParams {
  email: string;
  scene: "login" | "register";
}

export interface RegisterParams {
  email: string;
  code: string;
  invite_code: string;
}

export interface LoginParams {
  email: string;
  code: string;
}

export interface AuthResponse {
  data: {
    token: string;
    user: {
      id: number;
      email: string;
      role: string;
      nickname?: string;
    };
  };
}

export const authApi = {
  sendEmailCode: (params: SendCodeParams) =>
    request<{ message: string; data?: { code?: string } }>({
      method: "POST",
      url: "/auth/send-email-code",
      data: params,
    }),

  register: (params: RegisterParams) =>
    request<AuthResponse>({
      method: "POST",
      url: "/auth/register",
      data: params,
    }),

  login: (params: LoginParams) =>
    request<AuthResponse>({
      method: "POST",
      url: "/auth/login",
      data: params,
    }),
};
