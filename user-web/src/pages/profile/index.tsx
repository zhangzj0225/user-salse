import {
  Card,
  Descriptions,
  Tag,
  Button,
  Skeleton,
  Spin,
  App as AntdApp,
  Space,
  Typography,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { userApi } from "../../services/user";
import dayjs from "dayjs";

const { Text } = Typography;

const roleLabelMap: Record<string, string> = {
  admin: "管理员",
  agent: "代理",
  distributor: "分销商",
  customer: "客户",
};

const statusLabelMap: Record<string, string> = {
  active: "正常",
  inactive: "未激活",
  banned: "已封禁",
};

export default function ProfilePage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const { data: profileData, isLoading: profileLoading } = useQuery({
    queryKey: ["userProfile"],
    queryFn: () => userApi.getProfile(),
  });

  const { data: licenseData, isLoading: licenseLoading } = useQuery({
    queryKey: ["userLicense"],
    queryFn: () => userApi.getLicense(),
  });

  const inviteMutation = useMutation({
    mutationFn: () => userApi.generateInviteCode(),
    onSuccess: (res) => {
      message.success(`邀请码已生成：${res.data.code}`);
      queryClient.invalidateQueries({ queryKey: ["userProfile"] });
    },
  });

  const profile = profileData?.data;

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>我的</h2>

      <Spin spinning={profileLoading}>
        <Card title="个人信息" style={{ marginBottom: 16 }}>
          {profileLoading ? (
            <Skeleton active paragraph={{ rows: 3 }} />
          ) : (
            <Descriptions column={2} bordered>
              <Descriptions.Item label="用户ID">{profile?.id}</Descriptions.Item>
              <Descriptions.Item label="邮箱">{profile?.email}</Descriptions.Item>
              <Descriptions.Item label="昵称">{profile?.nickname || "-"}</Descriptions.Item>
              <Descriptions.Item label="角色">
                <Tag color="blue">{roleLabelMap[profile?.role ?? ""] ?? profile?.role}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={profile?.status === "active" ? "green" : "default"}>
                  {statusLabelMap[profile?.status ?? ""] ?? profile?.status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="注册时间">
                {profile?.created_at ? dayjs(profile.created_at).format("YYYY-MM-DD HH:mm") : "-"}
              </Descriptions.Item>
              <Descriptions.Item label="账户额度">
                {profile?.account_quota ?? 0} 个
              </Descriptions.Item>
              <Descriptions.Item label="已用额度">
                {profile?.account_used ?? 0} 个
              </Descriptions.Item>
            </Descriptions>
          )}
        </Card>
      </Spin>

      <Card title="邀请码" style={{ marginBottom: 16 }}>
        <Space direction="vertical" size="middle">
          <Space align="center">
            <Text type="secondary">我的邀请码：</Text>
            <Text copyable strong style={{ fontSize: 18 }}>
              {profile?.invite_code || "暂无"}
            </Text>
          </Space>
          <Button
            type="primary"
            loading={inviteMutation.isPending}
            onClick={() => inviteMutation.mutate()}
          >
            生成新邀请码
          </Button>
        </Space>
      </Card>

      <Card title="授权凭证">
        {licenseLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : licenseData?.data ? (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="授权码">{licenseData.data.license_code}</Descriptions.Item>
            <Descriptions.Item label="邮箱">{licenseData.data.email}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color="green">{licenseData.data.status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {licenseData.data.created_at
                ? dayjs(licenseData.data.created_at).format("YYYY-MM-DD HH:mm")
                : "-"}
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Text type="secondary">暂无授权凭证</Text>
        )}
      </Card>
    </div>
  );
}
