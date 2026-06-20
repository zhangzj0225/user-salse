import { request } from "./api";

export interface UserProfile {
  id: number;
  email: string;
  role: string;
  nickname: string;
  status: string;
  account_quota: number;
  account_used: number;
  created_at: string;
  invite_code: string;
}

export interface UserLicense {
  license_code: string;
  email: string;
  status: string;
  created_at: string;
}

export interface UserProfileResponse {
  data: UserProfile;
}

export interface UserLicenseResponse {
  data: UserLicense;
}

export interface InviteCodeResponse {
  data: { code: string };
}

export const userApi = {
  getProfile: () => request<UserProfileResponse>({ method: "GET", url: "/users/me" }),

  getLicense: () => request<UserLicenseResponse>({ method: "GET", url: "/users/me/license" }),

  generateInviteCode: () => request<InviteCodeResponse>({ method: "POST", url: "/invite-codes" }),
};
