import { Card, List, Tag, Button, Empty, App as AntdApp, Space, Typography } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationApi } from "../../services/notification";
import type { NotificationItem } from "../../services/notification";
import dayjs from "dayjs";

const { Text } = Typography;

const eventTypeLabelMap: Record<string, string> = {
  subordinate_registered: "下级注册",
  commission_credited: "佣金入账",
  ticket_approved: "提现已打款",
  ticket_rejected: "提现已拒绝",
  recharge_approved: "充值审核通过",
};

export default function NotificationsPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["notifications"],
    queryFn: () => notificationApi.list({ limit: 50, offset: 0 }),
  });

  const readMutation = useMutation({
    mutationFn: (id: number) => notificationApi.markAsRead(id),
    onSuccess: () => {
      message.success("已标记为已读");
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  const notifications = data?.notifications ?? [];

  function formatContent(item: NotificationItem): string {
    const c = item.content;
    if (typeof c === "string") return c;
    // 后端 content 为 JSON dict，提取关键字段显示
    if (c?.amount) return `金额: ¥${Number(c.amount).toFixed(2)}`;
    if (c?.message) return c.message as string;
    return JSON.stringify(c);
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>消息通知</h2>

      <Card>
        <List
          loading={isLoading}
          dataSource={notifications}
          locale={{ emptyText: <Empty description="暂无消息" /> }}
          renderItem={(item: NotificationItem) => (
            <List.Item
              actions={
                item.sent
                  ? undefined
                  : [
                      <Button
                        key="read"
                        type="link"
                        size="small"
                        loading={readMutation.isPending}
                        onClick={() => readMutation.mutate(item.id)}
                      >
                        标记已读
                      </Button>,
                    ]
              }
            >
              <List.Item.Meta
                title={
                  <Space>
                    {!item.sent && <Tag color="red">未读</Tag>}
                    <Text strong>{eventTypeLabelMap[item.event_type] ?? item.event_type}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs(item.created_at).format("YYYY-MM-DD HH:mm")}
                    </Text>
                  </Space>
                }
                description={
                  <Text style={{ marginBottom: 0, color: "#666" }}>{formatContent(item)}</Text>
                }
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
