import { request } from "./api";

export interface EarningsSummary {
  total_commission: number;
  withdrawn_total: number;
  available_balance: number;
}

export interface EarningsRecord {
  id: number;
  amount: number;
  type: string;
  from_user_email: string;
  from_user_nickname: string;
  status: string;
  created_at: string;
  remark: string;
}

export interface EarningsSummaryResponse {
  data: EarningsSummary;
}

export interface EarningsRecordsResponse {
  data: EarningsRecord[];
  total: number;
}

export interface EarningsRecordsParams {
  type?: string;
  limit?: number;
  offset?: number;
}

export const earningsApi = {
  getSummary: () =>
    request<EarningsSummaryResponse>({
      method: "GET",
      url: "/earnings/summary",
    }),

  getRecords: (params: EarningsRecordsParams) =>
    request<EarningsRecordsResponse>({
      method: "GET",
      url: "/earnings/records",
      params,
    }),
};
