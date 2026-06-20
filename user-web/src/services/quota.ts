import { request } from "./api";

// ── 后端 QuotaInfo（无 data 包装）──
export interface SalesRecord {
  recharge_id: number;
  child_email: string;
  amount: string;
  target_role?: string;
  approved_at?: string;
}

export interface QuotaInfo {
  role: string;
  account_quota: number;
  account_used: number;
  remaining: number;
  can_replenish: boolean;
  sales_records: SalesRecord[];
}

// ── 后端 SellAccountRequest ──
export interface CreateSaleParams {
  customer_email: string;
  verification_code: string;  // 后端字段名，非 code
}

// ── 后端 SellAccountResponse（无 data 包装）──
export interface SaleResponse {
  customer_id: number;
  recharge_id: number;
  remaining_quota: number;
}

export const quotaApi = {
  getQuota: () => request<QuotaInfo>({ method: "GET", url: "/quota" }),

  createSale: (params: CreateSaleParams) =>
    request<SaleResponse>({ method: "POST", url: "/sales", data: params }),
};
