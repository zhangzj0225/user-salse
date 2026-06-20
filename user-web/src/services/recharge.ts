import { request } from "./api";

export type RechargeAmount = 888 | 5000 | 10000;

export interface Recharge {
  id: number;
  amount: number;
  status: string;
  created_at: string;
}

export interface CreateRechargeResponse {
  data: { id: number; amount: number; status: string };
}

export interface RechargeListResponse {
  data: Recharge[];
  total: number;
}

export interface RechargeListParams {
  limit?: number;
  offset?: number;
}

export const rechargeApi = {
  create: (amount: RechargeAmount) =>
    request<CreateRechargeResponse>({
      method: "POST",
      url: "/recharges",
      data: { amount },
    }),

  list: (params?: RechargeListParams) =>
    request<RechargeListResponse>({
      method: "GET",
      url: "/recharges",
      params,
    }),
};
