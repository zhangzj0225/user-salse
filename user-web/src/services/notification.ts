import { request } from "./api";

// ── 后端通知项（notification_service 返回）──
export interface NotificationItem {
  id: number;
  event_type: string;      // 后端字段，非 type
  content: Record<string, unknown>;  // JSON dict，非纯字符串
  sent: boolean;           // 后端字段，非 is_read
  created_at: string;
}

// ── 后端响应: { notifications, total } ──
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
