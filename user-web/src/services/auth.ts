import { request } from "./api";

export interface SendCodeParams {
  email: string;
  scene: "login" | "sale_verify";
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

/** 后端 login 响应 body：{ data: { token, user } } */
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

  login: (params: LoginParams) =>
    request<AuthResponse>({
      method: "POST",
      url: "/auth/login",
      data: params,
    }),
};
