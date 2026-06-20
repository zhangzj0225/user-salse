import { request } from "./api";

// ── 后端 TicketInfo（无 data 包装）──
export interface Ticket {
  id: number;
  user_id: number;
  amount: string;
  payment_method: string;
  status: string;
  reject_reason?: string;
  processed_by?: number;
  processed_at?: string;
  created_at: string;
}

// ── 后端 CreateTicketRequest ──
export interface CreateTicketParams {
  amount: string;  // 后端 str（防浮点精度）
  payment_method: string;
}

// ── 后端 CreateTicketResponse（无 data 包装）──
export interface CreateTicketResponse {
  ticket_id: number;
  amount: string;
  status: string;
  available_balance: string;
}

// ── 后端 TicketListResponse: { tickets, total } ──
export interface TicketListResponse {
  tickets: Ticket[];
  total: number;
}

export interface TicketListParams {
  status?: string;
  limit?: number;
  offset?: number;
}

export const ticketApi = {
  create: (params: CreateTicketParams) =>
    request<CreateTicketResponse>({
      method: "POST",
      url: "/users/me/tickets",
      data: params,
    }),

  list: (params?: TicketListParams) =>
    request<TicketListResponse>({
      method: "GET",
      url: "/users/me/tickets",
      params,
    }),
};
