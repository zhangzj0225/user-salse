import { Card, List, Tag, Button, Empty, App as AntdApp, Space, Typography } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { notificationApi } from "../../services/notification";
import type { NotificationItem } from "../../services/notification";
import dayjs from "dayjs";

const { Text, Paragraph } = Typography;

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
                item.is_read
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
                    {!item.is_read && <Tag color="red">未读</Tag>}
                    <Text strong>{item.title}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {dayjs(item.created_at).format("YYYY-MM-DD HH:mm")}
                    </Text>
                  </Space>
                }
                description={<Paragraph style={{ marginBottom: 0 }}>{item.content}</Paragraph>}
              />
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
