import { Card, Row, Col, Button, Table, Tag, App as AntdApp } from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { rechargeApi } from "../../services/recharge";
import type { RechargeAmount, Recharge } from "../../services/recharge";
import dayjs from "dayjs";

const amountOptions: { value: RechargeAmount; label: string }[] = [
  { value: 888, label: "¥888" },
  { value: 5000, label: "¥5,000" },
  { value: 10000, label: "¥10,000" },
];

const statusColorMap: Record<string, string> = {
  pending: "orange",
  approved: "green",
  rejected: "red",
};

const statusLabelMap: Record<string, string> = {
  pending: "待审核",
  approved: "已通过",
  rejected: "已拒绝",
};

export default function RechargePage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["recharges"],
    queryFn: () => rechargeApi.list({ limit: 50, offset: 0 }),
  });

  const createMutation = useMutation({
    mutationFn: (amount: RechargeAmount) => rechargeApi.create(amount),
    onSuccess: () => {
      message.success("充值订单已创建");
      queryClient.invalidateQueries({ queryKey: ["recharges"] });
    },
  });

  const columns = [
    {
      title: "订单ID",
      dataIndex: "id",
      key: "id",
      width: 80,
    },
    {
      title: "充值金额",
      dataIndex: "amount",
      key: "amount",
      render: (amount: number) => `¥${Number(amount).toFixed(2)}`,
    },
    {
      title: "状态",
      dataIndex: "status",
      key: "status",
      render: (status: string) => (
        <Tag color={statusColorMap[status] ?? "default"}>{statusLabelMap[status] ?? status}</Tag>
      ),
    },
    {
      title: "创建时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? dayjs(text).format("YYYY-MM-DD HH:mm") : "-"),
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>充值</h2>

      <Card title="选择充值金额" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          {amountOptions.map((opt) => (
            <Col span={8} key={opt.value}>
              <Button
                block
                size="large"
                loading={createMutation.isPending}
                style={{ height: 80, fontSize: 20, fontWeight: 600 }}
                onClick={() => createMutation.mutate(opt.value)}
              >
                {opt.label}
              </Button>
            </Col>
          ))}
        </Row>
      </Card>

      <Card title="充值记录">
        <Table<Recharge>
          columns={columns}
          dataSource={data?.data ?? []}
          loading={isLoading}
          rowKey="id"
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      </Card>
    </div>
  );
}
