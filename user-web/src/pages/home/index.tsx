import { Card, Row, Col, Statistic, Button, Space, Tag, Skeleton } from "antd";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  WalletOutlined,
  DollarOutlined,
  TeamOutlined,
  MoneyCollectOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { earningsApi } from "../../services/earnings";
import { quotaApi } from "../../services/quota";
import { useAuthStore } from "../../stores/auth";

const roleLabelMap: Record<string, string> = {
  user: "普通用户",
  member: "888会员",
  distributor: "经销商",
  agent: "代理",
};

const roleColorMap: Record<string, string> = {
  user: "default",
  member: "green",
  distributor: "blue",
  agent: "gold",
};

export default function HomePage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  const { data: quotaData, isLoading: quotaLoading } = useQuery({
    queryKey: ["quota"],
    queryFn: () => quotaApi.getQuota(),
  });

  const { data: earningsData, isLoading: earningsLoading } = useQuery({
    queryKey: ["earningsSummary"],
    queryFn: () => earningsApi.getEarnings(),
  });

  const role = user?.role ?? "";

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space size="large" align="center">
          <h2 style={{ margin: 0 }}>欢迎回来，{user?.nickname || user?.email}</h2>
          <Tag color={roleColorMap[role] ?? "default"}>{roleLabelMap[role] ?? role}</Tag>
        </Space>
      </Card>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            {quotaLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="可用额度"
                value={quotaData?.remaining ?? 0}
                suffix="个"
                prefix={<WalletOutlined />}
              />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {earningsLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="记账余额"
                value={Number(earningsData?.summary?.pending_balance ?? 0)}
                prefix="¥"
              />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {earningsLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="可用余额"
                value={Number(earningsData?.summary?.available_balance ?? 0)}
                prefix="¥"
                valueStyle={{ color: "#3f8600" }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="快捷操作">
        <Space wrap size="middle">
          <Button type="primary" icon={<DollarOutlined />} onClick={() => navigate("/recharge")}>
            去充值
          </Button>
          <Button icon={<TeamOutlined />} onClick={() => navigate("/team")}>
            我的团队
          </Button>
          <Button icon={<MoneyCollectOutlined />} onClick={() => navigate("/earnings")}>
            我的收益
          </Button>
          <Button icon={<WalletOutlined />} onClick={() => navigate("/withdrawal")}>
            提现
          </Button>
          <Button icon={<UserOutlined />} onClick={() => navigate("/profile")}>
            个人中心
          </Button>
        </Space>
      </Card>
    </div>
  );
}
