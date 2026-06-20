import { request } from "./api";

export interface NotificationItem {
  id: number;
  title: string;
  content: string;
  is_read: boolean;
  type: string;
  created_at: string;
}

export interface NotificationsResponse {
  notifications: NotificationItem[];
  total: number;
}

export interface NotificationReadResponse {
  success: boolean;
}

export interface NotificationListParams {
  limit?: number;
  offset?: number;
}

export const notificationApi = {
  list: (params?: NotificationListParams) =>
    request<NotificationsResponse>({
      method: "GET",
      url: "/users/me/notifications",
      params,
    }),

  markAsRead: (id: number) =>
    request<NotificationReadResponse>({
      method: "POST",
      url: `/users/me/notifications/${id}/read`,
    }),
};
