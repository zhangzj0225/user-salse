import { useState } from "react";
import { Row, Col, Card, Table, Select, Tag } from "antd";
import { useQuery } from "@tanstack/react-query";
import { earningsApi } from "../../services/earnings";
import type { EarningsRecord } from "../../services/earnings";
import dayjs from "dayjs";

const typeOptions = [
  { label: "全部", value: "" },
  { label: "首单奖励", value: "first_reward" },
  { label: "复购提成", value: "recurring" },
];

const typeLabelMap: Record<string, string> = {
  first_reward: "首单奖励",
  recurring: "复购提成",
};

const PAGE_SIZE = 20;

export default function EarningsPage() {
  const [type, setType] = useState("");
  const [page, setPage] = useState(1);

  const { data: summaryData, isLoading: summaryLoading } = useQuery({
    queryKey: ["earningsSummary"],
    queryFn: () => earningsApi.getSummary(),
  });

  const { data: recordsData, isLoading: recordsLoading } = useQuery({
    queryKey: ["earningsRecords", type, page],
    queryFn: () =>
      earningsApi.getRecords({
        type: type || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      }),
  });

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
      dataIndex: "from_user_email",
      key: "from_user_email",
      render: (email: string, record: EarningsRecord) =>
        record.from_user_nickname ? `${record.from_user_nickname} (${email})` : email || "-",
    },
    {
      title: "金额",
      dataIndex: "amount",
      key: "amount",
      render: (amount: number) => (
        <span style={{ color: "#3f8600" }}>¥{Number(amount).toFixed(2)}</span>
      ),
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
    },
    {
      title: "备注",
      dataIndex: "remark",
      key: "remark",
      render: (text: string) => text || "-",
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
          <Card loading={summaryLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>累计佣金（记账余额）</span>}
              description={
                <span style={{ fontSize: 24, color: "#1677ff" }}>
                  ¥{Number(summaryData?.data.total_commission ?? 0).toFixed(2)}
                </span>
              }
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={summaryLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>已提现金额</span>}
              description={
                <span style={{ fontSize: 24 }}>
                  ¥{Number(summaryData?.data.withdrawn_total ?? 0).toFixed(2)}
                </span>
              }
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={summaryLoading}>
            <Card.Meta
              title={<span style={{ fontSize: 14 }}>可用余额</span>}
              description={
                <span style={{ fontSize: 24, color: "#3f8600" }}>
                  ¥{Number(summaryData?.data.available_balance ?? 0).toFixed(2)}
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
          dataSource={recordsData?.data ?? []}
          loading={recordsLoading}
          rowKey="id"
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: recordsData?.total ?? 0,
            onChange: (p) => setPage(p),
            showSizeChanger: false,
          }}
        />
      </Card>
    </div>
  );
}
