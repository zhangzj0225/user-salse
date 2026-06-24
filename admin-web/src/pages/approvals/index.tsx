import { PageContainer } from '@ant-design/pro-components';
import { useRequest, request } from '@umijs/max';
import {
  Table,
  Button,
  Tabs,
  Modal,
  Form,
  Input,
  Tag,
  Space,
  message,
} from 'antd';
import { useState } from 'react';
import dayjs from 'dayjs';

const STATUS_TABS = [
  { key: 'pending', label: '待审核' },
  { key: 'paid', label: '已支付' },
  { key: 'failed', label: '失败' },
];

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  paid: 'green',
  failed: 'red',
};

export default function ApprovalsPage() {
  const [status, setStatus] = useState('pending');
  const [approveRecord, setApproveRecord] = useState<any>(null);
  const [rejectRecord, setRejectRecord] = useState<any>(null);
  const [approveForm] = Form.useForm();
  const [rejectForm] = Form.useForm();
  const [actionLoading, setActionLoading] = useState(false);

  const { data, loading, refresh } = useRequest(
    () =>
      request('/api/v1/admin/payments', {
        params: { status },
      }),
    { refreshDeps: [status] },
  );

  const list = data?.items || (Array.isArray(data) ? data : []);

  const handleApprove = async () => {
    const values = await approveForm.validateFields();
    setActionLoading(true);
    try {
      await request(`/api/v1/admin/payments/${approveRecord.id}/approve`, {
        method: 'POST',
        data: { referral_code: values.referral_code || undefined },
      });
      message.success('已批准');
      setApproveRecord(null);
      approveForm.resetFields();
      refresh();
    } catch {
      message.error('操作失败');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    const values = await rejectForm.validateFields();
    setActionLoading(true);
    try {
      await request(`/api/v1/admin/payments/${rejectRecord.id}/reject`, {
        method: 'POST',
        data: { reject_reason: values.reject_reason },
      });
      message.success('已拒绝');
      setRejectRecord(null);
      rejectForm.resetFields();
      refresh();
    } catch {
      message.error('操作失败');
    } finally {
      setActionLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '邮箱', dataIndex: 'email' },
    {
      title: '金额',
      dataIndex: 'amount',
      render: (v: number) => `¥${v ?? 0}`,
    },
    { title: '目标角色', dataIndex: 'target_role' },
    {
      title: '推荐码',
      dataIndex: 'referral_code',
      render: (v: string) => v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      render: (t: string) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'),
    },
    {
      title: '操作',
      width: 150,
      render: (_: any, record: any) =>
        record.status === 'pending' ? (
          <Space>
            <Button type="link" onClick={() => setApproveRecord(record)}>
              批准
            </Button>
            <Button type="link" danger onClick={() => setRejectRecord(record)}>
              拒绝
            </Button>
          </Space>
        ) : (
          '-'
        ),
    },
  ];

  return (
    <PageContainer>
      <Tabs
        items={STATUS_TABS}
        activeKey={status}
        onChange={(k) => setStatus(k)}
      />
      <Table
        columns={columns}
        dataSource={list}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="批准支付"
        open={!!approveRecord}
        onOk={handleApprove}
        onCancel={() => {
          setApproveRecord(null);
          approveForm.resetFields();
        }}
        confirmLoading={actionLoading}
      >
        <Form form={approveForm} layout="vertical">
          <Form.Item name="referral_code" label="推荐码（选填）">
            <Input placeholder="可补填推荐码" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="拒绝支付"
        open={!!rejectRecord}
        onOk={handleReject}
        onCancel={() => {
          setRejectRecord(null);
          rejectForm.resetFields();
        }}
        confirmLoading={actionLoading}
      >
        <Form form={rejectForm} layout="vertical">
          <Form.Item
            name="reject_reason"
            label="拒绝原因"
            rules={[{ required: true, message: '请填写拒绝原因' }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </PageContainer>
  );
}
