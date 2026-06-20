import { request } from "./api";

// ── 后端 TeamNode schema ──
export interface TeamMember {
  user_id: number;
  nickname: string | null;
  role: string;
  created_at: string;
  direct_downline_count: number;
  children: TeamMember[];
}

// ── 后端 UpstreamNode schema ──
export interface UpstreamMember {
  user_id: number;
  nickname: string | null;
  role: string;
  level: number;
}

// ── 后端 TeamTreeResponse: { total_count, root } ──
export interface TeamTreeResponse {
  total_count: number;
  root: TeamMember;
}

// ── 后端 UpstreamChainResponse: { chain } ──
export interface UpstreamChainResponse {
  chain: UpstreamMember[];
}

export const teamApi = {
  getDownstream: () =>
    request<TeamTreeResponse>({
      method: "GET",
      url: "/users/me/team",
    }),

  getUpstream: () =>
    request<UpstreamChainResponse>({
      method: "GET",
      url: "/users/me/upstream",
    }),
};
