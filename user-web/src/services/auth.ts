import api from "./api";

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

export const authApi = {
  sendEmailCode: (params: SendCodeParams) =>
    api.post("/auth/send-email-code", params),

  register: (params: RegisterParams) =>
    api.post("/auth/register", params),

  login: (params: LoginParams) =>
    api.post("/auth/login", params),
};
