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
import { useAuthStore } from "../../stores/auth";

export default function SalesPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const [form] = Form.useForm();

  const canSales = user?.role === "agent" || user?.role === "distributor";

  const { data: quotaData, isLoading } = useQuery({
    queryKey: ["quota"],
    queryFn: () => quotaApi.getQuota(),
  });

  const createMutation = useMutation({
    mutationFn: (values: { customer_email: string; code: string }) => quotaApi.createSale(values),
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
              <Statistic title="账户额度" value={quotaData?.data.account_quota ?? 0} suffix="个" />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            {isLoading ? (
              <Skeleton active paragraph={{ rows: 1 }} />
            ) : (
              <Statistic title="已用额度" value={quotaData?.data.account_used ?? 0} suffix="个" />
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
                value={quotaData?.data.remaining ?? 0}
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
            name="code"
            label="授权码"
            rules={[{ required: true, message: "请输入授权码" }]}
          >
            <Input placeholder="请输入授权码" />
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
