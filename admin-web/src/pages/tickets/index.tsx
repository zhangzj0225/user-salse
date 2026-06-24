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
  { key: '', label: '全部' },
  { key: 'pending', label: '待处理' },
  { key: 'paid', label: '已打款' },
  { key: 'rejected', label: '已拒绝' },
];

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  paid: 'green',
  rejected: 'red',
};

export default function TicketsPage() {
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [rejectRecord, setRejectRecord] = useState<any>(null);
  const [rejectForm] = Form.useForm();
  const [approvingId, setApprovingId] = useState<number | null>(null);
  const [rejectLoading, setRejectLoading] = useState(false);
  const limit = 20;

  const { data, loading, refresh } = useRequest(
    () =>
      request('/api/v1/admin/tickets', {
        params: {
          status: status || undefined,
          limit,
          offset: (page - 1) * limit,
        },
      }),
    { refreshDeps: [status, page] },
  );

  const list = data?.items || (Array.isArray(data) ? data : []);
  const total = data?.total ?? list.length;

  const handleApprove = async (id: number) => {
    setApprovingId(id);
    try {
      await request(`/api/v1/admin/tickets/${id}/approve`, {
        method: 'POST',
      });
      message.success('已确认打款');
      refresh();
    } catch {
      message.error('操作失败');
    } finally {
      setApprovingId(null);
    }
  };

  const handleReject = async () => {
    const values = await rejectForm.validateFields();
    setRejectLoading(true);
    try {
      await request(`/api/v1/admin/tickets/${rejectRecord.id}/reject`, {
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
      setRejectLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '用户邮箱', dataIndex: 'user_email' },
    {
      title: '金额',
      dataIndex: 'amount',
      render: (v: number) => `¥${v ?? 0}`,
    },
    { title: '收款方式', dataIndex: 'payment_method' },
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
            <Button
              type="link"
              onClick={() => handleApprove(record.id)}
              loading={approvingId === record.id}
            >
              已打款
            </Button>
            <Button
              type="link"
              danger
              onClick={() => setRejectRecord(record)}
            >
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
        onChange={(k) => {
          setStatus(k);
          setPage(1);
        }}
      />
      <Table
        columns={columns}
        dataSource={list}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize: limit,
          total,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 条`,
        }}
      />

      <Modal
        title="拒绝工单"
        open={!!rejectRecord}
        onOk={handleReject}
        onCancel={() => {
          setRejectRecord(null);
          rejectForm.resetFields();
        }}
        confirmLoading={rejectLoading}
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
