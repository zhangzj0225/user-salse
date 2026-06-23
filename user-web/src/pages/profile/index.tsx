import {
  Card,
  Descriptions,
  Tag,
  Skeleton,
  Spin,
  Space,
  Typography,
} from "antd";
import { useQuery } from "@tanstack/react-query";
import { userApi } from "../../services/user";
import dayjs from "dayjs";

const { Text } = Typography;

const roleLabelMap: Record<string, string> = {
  distributor: "经销商",
  agent: "代理",
};

const statusLabelMap: Record<string, string> = {
  pending: "待激活",
  active: "正常",
  rejected: "已拒绝",
};

export default function ProfilePage() {
  const { data: profileData, isLoading: profileLoading } = useQuery({
    queryKey: ["userProfile"],
    queryFn: () => userApi.getProfile(),
  });

  const { data: licenseData, isLoading: licenseLoading } = useQuery({
    queryKey: ["userLicense"],
    queryFn: () => userApi.getLicense(),
  });

  const { data: referralData, isLoading: referralLoading } = useQuery({
    queryKey: ["referralCode"],
    queryFn: () => userApi.getReferralCode(),
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
            </Descriptions>
          )}
        </Card>
      </Spin>

      <Card title="推荐码" style={{ marginBottom: 16 }}>
        {referralLoading ? (
          <Skeleton active paragraph={{ rows: 1 }} />
        ) : referralData?.data?.code ? (
          <Space direction="vertical" size="middle">
            <Text copyable style={{ fontSize: 18, fontWeight: 600 }}>
              {referralData.data.code}
            </Text>
          </Space>
        ) : (
          <Text type="secondary">暂无推荐码</Text>
        )}
      </Card>

      <Card title="授权凭证">
        {licenseLoading ? (
          <Skeleton active paragraph={{ rows: 2 }} />
        ) : licenseData ? (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="授权码">{licenseData.code}</Descriptions.Item>
            <Descriptions.Item label="来源">{licenseData.source}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={licenseData.status === "unused" ? "green" : "orange"}>
                {licenseData.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {licenseData.created_at
                ? dayjs(licenseData.created_at).format("YYYY-MM-DD HH:mm")
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
