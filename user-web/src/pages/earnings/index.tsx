import { useState } from "react";
import { Row, Col, Card, Table, Select, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { earningsApi } from "../../services/earnings";
import type { EarningsRecord } from "../../services/earnings";
import dayjs from "dayjs";

const typeOptions = [
  { label: "全部", value: "" },
  { label: "首次奖励", value: "first_reward" },
  { label: "后续收益", value: "followup_reward" },
  { label: "长期奖励", value: "team_bonus" },
  { label: "推荐返佣", value: "recommend" },
  { label: "销售佣金", value: "sale_commission" },
];

const typeLabelMap: Record<string, string> = {
  first_reward: "首次奖励",
  followup_reward: "后续收益",
  team_bonus: "长期奖励",
  recommend: "推荐返佣",
  sale_commission: "销售佣金",
};

const PAGE_SIZE = 20;

export default function EarningsPage() {
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["earnings", type, page],
    queryFn: () =>
      earningsApi.getEarnings({
        type: type || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
  });

  // 后端汇总字段为 str（金额），前端直接展示，number 转换仅用于格式化
  const summary = data?.summary;

  const columns = [
    {
      title: "ID",
      dataIndex: "id",
      key: "id",
      width: 80,
    },
    {
      title: "类型",
      dataIndex: "type",
      key: "type",
      render: (t: string) => <Tag color="orange">{typeLabelMap[t] ?? t}</Tag>,
    },
    {
      title: "来源用户",
      dataIndex: "source_email",
      key: "source_email",
      render: (email: string | null) => email || "-",
    },
    {
      title: "金额",
      dataIndex: "amount",
      key: "amount",
      render: (amount: string) => (
        <span style={{ color: "#3f8600" }}>¥{Number(amount).toFixed(2)}</span>
      ),
    },
    {
      title: "业务ID",
      dataIndex: "business_id",
      key: "business_id",
      ellipsis: true,
    },
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? dayjs(text).format("YYYY-MM-DD HH:mm") : "-"),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>我的收益</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card loading={isLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>累计佣金（记账余额）</span>}
              description={
                <span style={{ fontSize: 24, color: "#1677ff" }}>
                  ¥{Number(summary?.pending_balance ?? 0).toFixed(2)}
                </span>
              }
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={isLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>已提现金额</span>}
              description={
                <span style={{ fontSize: 24 }}>
                  ¥{Number(summary?.withdrawn_total ?? 0).toFixed(2)}
                </span>
              }
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={isLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>可用余额</span>}
              description={
                <span style={{ fontSize: 24, color: "#3f8600" }}>
                  ¥{Number(summary?.available_balance ?? 0).toFixed(2)}
                </span>
              }
            />
          </Card>
        </Col>
      </Row>

      <Card title="收益记录">
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 8 }}>类型筛选：</span>
          <Select
            value={type}
            onChange={(v) => {
              setType(v);
              setPage(1);
            }}
            options={typeOptions}
            style={{ width: 160 }}
          />
        </div>
        <Table<EarningsRecord>
          columns={columns}
          dataSource={data?.records ?? []}
          loading={isLoading}
          rowKey="id"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: data?.total ?? 0,
            onChange: (p) => setPage(p),
            showSizeChanger: false,
          }}
        />
      </Card>
    </div>
  );
}
