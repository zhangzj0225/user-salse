import {
  Card,
  Row,
  Col,
  Statistic,
  Form,
  Input,
  InputNumber,
  Select,
  Button,
  Table,
  Tag,
  Skeleton,
  App as AntdApp,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { earningsApi } from "../../services/earnings";
import { ticketApi } from "../../services/ticket";
import type { Ticket } from "../../services/ticket";
import dayjs from "dayjs";

const paymentMethodOptions = [
  { label: "支付宝", value: "alipay" },
  { label: "微信", value: "wechat" },
  { label: "银行卡", value: "bank_card" },
];

const paymentMethodLabelMap: Record<string, string> = {
  alipay: "支付宝",
  wechat: "微信",
  bank_card: "银行卡",
};

const statusColorMap: Record<string, string> = {
  pending: "orange",
  paid: "green",
  rejected: "red",
};

const statusLabelMap: Record<string, string> = {
  pending: "待审核",
  paid: "已打款",
  rejected: "已拒绝",
};

export default function WithdrawalPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const [form] = Form.useForm();

  const { data: summaryData, isLoading: summaryLoading } = useQuery({
    queryKey: ["earningsSummary"],
    queryFn: () => earningsApi.getSummary(),
  });

  const { data: ticketsData, isLoading: ticketsLoading } = useQuery({
    queryKey: ["tickets", "pending"],
    queryFn: () => ticketApi.list({ limit: 50, offset: 0 }),
  });

  const createMutation = useMutation({
    mutationFn: (values: {
      amount: number;
      payment_method: string;
      payment_info: string;
    }) => ticketApi.create(values),
    onSuccess: () => {
      message.success("提现申请已提交");
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ["tickets"] });
      queryClient.invalidateQueries({ queryKey: ["earningsSummary"] });
    },
  });

  const columns = [
    {
      title: "工单ID",
      dataIndex: "id",
      key: "id",
      width: 80,
    },
    {
      title: "提现金额",
      dataIndex: "amount",
      key: "amount",
      render: (amount: number) => `¥${Number(amount).toFixed(2)}`,
    },
    {
      title: "收款方式",
      dataIndex: "payment_method",
      key: "payment_method",
      render: (method: string) => paymentMethodLabelMap[method] ?? method,
    },
    {
      title: "收款信息",
      dataIndex: "payment_info",
      key: "payment_info",
      render: (text: string) => text || "-",
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

  const availableBalance = summaryData?.data.available_balance ?? 0;

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>提现</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            {summaryLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="可用余额"
                value={availableBalance}
                prefix="¥"
                valueStyle={{ color: "#3f8600" }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="申请提现" style={{ marginBottom: 16 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
          style={{ maxWidth: 480 }}
        >
          <Form.Item
            name="amount"
            label="提现金额"
            rules={[
              { required: true, message: "请输入提现金额" },
              {
                validator: (_, value) => {
                  if (value == null) return Promise.resolve();
                  if (value <= 0) {
                    return Promise.reject(new Error("提现金额必须大于0"));
                  }
                  if (value > availableBalance) {
                    return Promise.reject(new Error("提现金额不能超过可用余额"));
                  }
                  return Promise.resolve();
                },
              },
            ]}
          >
            <InputNumber
              style={{ width: "100%" }}
              min={0}
              max={availableBalance}
              precision={2}
              placeholder="请输入提现金额"
            />
          </Form.Item>
          <Form.Item
            name="payment_method"
            label="收款方式"
            rules={[{ required: true, message: "请选择收款方式" }]}
          >
            <Select placeholder="请选择收款方式" options={paymentMethodOptions} />
          </Form.Item>
          <Form.Item
            name="payment_info"
            label="收款信息"
            rules={[{ required: true, message: "请输入收款信息" }]}
          >
            <Input.TextArea rows={2} placeholder="请输入收款账号/信息" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              提交提现申请
            </Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="提现记录">
        <Table<Ticket>
          columns={columns}
          dataSource={ticketsData?.data ?? []}
          loading={ticketsLoading}
          rowKey="id"
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      </Card>
    </div>
  );
}
