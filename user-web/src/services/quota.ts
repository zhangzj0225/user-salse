import { request } from "./api";

export interface QuotaInfo {
  account_quota: number;
  account_used: number;
  remaining: number;
}

export interface QuotaResponse {
  data: QuotaInfo;
}

export interface SaleResponse {
  data: { id: number };
}

export interface CreateSaleParams {
  customer_email: string;
  code: string;
}

export const quotaApi = {
  getQuota: () => request<QuotaResponse>({ method: "GET", url: "/quota" }),

  createSale: (params: CreateSaleParams) =>
    request<SaleResponse>({ method: "POST", url: "/sales", data: params }),
};
