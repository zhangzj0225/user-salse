import {
  Card,
  Row,
  Col,
  Statistic,
  Form,
  Input,
  Button,
  Skeleton,
  Result,
  App as AntdApp,
} from "antd";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { quotaApi } from "../../services/quota";
import { authApi } from "../../services/auth";
import { useAuthStore } from "../../stores/auth";
import { useState, useRef } from "react";

export default function SalesPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [form] = Form.useForm();
  const [sending, setSending] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const canSales = user?.role === "agent" || user?.role === "distributor";

  const { data: quotaData, isLoading } = useQuery({
    queryKey: ["quota"],
    queryFn: () => quotaApi.getQuota(),
  });

  const startCountdown = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCountdown(60);
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) { clearInterval(timer); return 0; }
        return c - 1;
      });
    }, 1000);
    timerRef.current = timer;
  };

  const handleSendVerificationCode = async () => {
    const email = form.getFieldValue("customer_email");
    if (!email) { message.warning("请先输入客户邮箱"); return; }
    setSending(true);
    try {
      await authApi.sendEmailCode({ email, scene: "sale_verify" });
      message.success("验证码已发送");
      startCountdown();
    } finally {
      setSending(false);
    }
  };

  const createMutation = useMutation({
    mutationFn: (values: { customer_email: string; verification_code: string }) =>
      quotaApi.createSale(values),
    onSuccess: () => {
      message.success("销售成功");
      form.resetFields();
      queryClient.invalidateQueries({ queryKey: ["quota"] });
    },
  });

  if (!canSales) {
    return <Result status="403" title="无权限" subTitle="仅代理/分销商可访问销售页面" />;
  }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>销售账号</h2>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            {isLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic title="账户额度" value={quotaData?.account_quota ?? 0} suffix="个" />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {isLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic title="已用额度" value={quotaData?.account_used ?? 0} suffix="个" />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {isLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic
                title="剩余额度"
                value={quotaData?.remaining ?? 0}
                suffix="个"
                valueStyle={{ color: "#3f8600" }}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card title="销售账号">
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => createMutation.mutate(values)}
          style={{ maxWidth: 480 }}
        >
          <Form.Item
            name="customer_email"
            label="客户邮箱"
            rules={[
              { required: true, message: "请输入客户邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input placeholder="请输入客户邮箱" />
          </Form.Item>
          <Form.Item
            name="verification_code"
            label="邮箱验证码"
            rules={[{ required: true, message: "请输入邮箱验证码" }]}
          >
            <Input.Search
              placeholder="请输入验证码"
              maxLength={6}
              enterButton={countdown > 0 ? `${countdown}s` : "获取验证码"}
              disabled={countdown > 0 || sending}
              loading={sending && countdown === 0}
              onSearch={handleSendVerificationCode}
            />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={createMutation.isPending}>
              确认销售
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
