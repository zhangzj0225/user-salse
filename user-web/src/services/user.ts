import { request } from "./api";

// ── 后端 LicenseInfo（无 data 包装）──
export interface UserLicense {
  code: string;
  source: string;
  status: string;
  activated_at?: string;
  expires_at?: string;
  created_at: string;
}

// ── 后端 UserInfo（main.py /users/me / /admin/me）──
export interface UserProfile {
  id: number;
  email: string;
  role: string;
  nickname?: string;
  status: string;
  avatar_url?: string;
}

export interface ReferralCodeResponse {
  data: { code: string };
}

export const userApi = {
  getProfile: () => request<{ data: UserProfile }>({ method: "GET", url: "/users/me" }),

  getLicense: () => request<UserLicense>({ method: "GET", url: "/users/me/license" }),

  getReferralCode: () => request<ReferralCodeResponse>({ method: "GET", url: "/referral-code" }),
};
