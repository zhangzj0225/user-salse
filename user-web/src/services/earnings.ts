import { request } from "./api";

// ── 后端 EarningsSummary: { pending_balance, withdrawn_total, available_balance }（均为 str）──
export interface EarningsSummary {
  pending_balance: string;
  withdrawn_total: string;
  available_balance: string;
}

// ── 后端 EarningsRecord ──
export interface EarningsRecord {
  id: number;
  amount: string;
  type: string;
  source_user_id: number | null;
  source_email: string | null;
  business_id: string;
  created_at: string;
}

// ── 后端 EarningsListResponse: { summary, records, total } ──
export interface EarningsListResponse {
  summary: EarningsSummary;
  records: EarningsRecord[];
  total: number;
}

export interface EarningsListParams {
  type?: string;
  limit?: number;
  offset?: number;
}

export const earningsApi = {
  /** 收益汇总 + 明细，单端点返回二者（后端无独立 /summary /records）。 */
  getEarnings: (params?: EarningsListParams) =>
    request<EarningsListResponse>({
      method: "GET",
      url: "/users/me/earnings",
      params,
    }),
};
