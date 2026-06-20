import { request } from "./api";

export interface TeamMember {
  id: number;
  email: string;
  nickname: string;
  role: string;
  created_at: string;
  children_count: number;
}

export interface UpstreamMember {
  id: number;
  email: string;
  nickname: string;
  role: string;
}

export interface DownstreamResponse {
  data: TeamMember[];
}

export interface UpstreamResponse {
  data: UpstreamMember[];
}

export const teamApi = {
  getDownstream: () => request<DownstreamResponse>({ method: "GET", url: "/team/downstream" }),

  getUpstream: () => request<UpstreamResponse>({ method: "GET", url: "/team/upstream" }),
};
