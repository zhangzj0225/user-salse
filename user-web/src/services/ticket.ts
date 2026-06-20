import { request } from "./api";

export interface Ticket {
  id: number;
  amount: number;
  status: string;
  payment_method: string;
  payment_info: string;
  created_at: string;
}

export interface CreateTicketParams {
  amount: number;
  payment_method: string;
  payment_info: string;
}

export interface CreateTicketResponse {
  data: { id: number; amount: number; status: string };
}

export interface TicketListResponse {
  data: Ticket[];
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
