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

export interface UserInfo {
  id: number;
  email: string;
  role: string;
  nickname?: string;
}

/** 后端 send-email-code 响应 body：{ data: { message, code? } } */
export interface SendCodeResponse {
  data: {
    message: string;
    code?: string;
  };
}

/** 后端 login/register 响应 body：{ data: { token, user } } */
export interface AuthResponse {
  data: {
    token: string;
    user: UserInfo;
  };
}

export const authApi = {
  sendEmailCode: (params: SendCodeParams) =>
    request<SendCodeResponse>({
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
