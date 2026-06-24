import { PageContainer } from '@ant-design/pro-components';
import { useRequest, request } from '@umijs/max';
import {
  Table,
  Button,
  Input,
  Select,
  Space,
  Modal,
  Form,
  Drawer,
  Tag,
  Spin,
  message,
} from 'antd';
import { useState } from 'react';
import dayjs from 'dayjs';

const ROLE_OPTIONS = [
  { label: '代理', value: 'agent' },
  { label: '经销商', value: 'dealer' },
];

const ROLE_LABEL: Record<string, string> = {
  agent: '代理',
  dealer: '经销商',
};

export default function UsersPage() {
  const [search, setSearch] = useState('');
  const [role, setRole] = useState<string | undefined>();
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm] = Form.useForm();
  const [createLoading, setCreateLoading] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const limit = 20;

  const { data, loading, refresh } = useRequest(
    () =>
      request('/api/v1/admin/users', {
        params: { search, role, limit, offset: (page - 1) * limit },
      }),
    { refreshDeps: [search, role, page] },
  );

  const list = data?.items || (Array.isArray(data) ? data : []);
  const total = data?.total ?? list.length;

  const showDetail = async (id: number) => {
    setDetailId(id);
    setDetail(null);
    setDetailLoading(true);
    try {
      const res = await request(`/api/v1/admin/users/${id}`);
      setDetail(res);
    } catch {
      message.error('获取用户详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const handleCreate = async () => {
    const values = await createForm.validateFields();
    setCreateLoading(true);
    try {
      await request('/api/v1/admin/users/create', {
        method: 'POST',
        data: values,
      });
      message.success('用户创建成功');
      setCreateOpen(false);
      createForm.resetFields();
      refresh();
    } catch {
      message.error('创建用户失败');
    } finally {
      setCreateLoading(false);
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 80 },
    { title: '邮箱', dataIndex: 'email' },
    {
      title: '角色',
      dataIndex: 'role',
      render: (r: string) => <Tag>{ROLE_LABEL[r] || r}</Tag>,
    },
    { title: '额度', dataIndex: 'quota' },
    {
      title: '注册时间',
      dataIndex: 'created_at',
      render: (t: string) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'),
    },
  ];

  return (
    <PageContainer>
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索邮箱"
          onSearch={(v) => {
            setSearch(v);
            setPage(1);
          }}
          allowClear
          style={{ width: 250 }}
        />
        <Select
          placeholder="角色筛选"
          allowClear
          style={{ width: 150 }}
          options={ROLE_OPTIONS}
          onChange={(v) => {
            setRole(v);
            setPage(1);
          }}
        />
        <Button type="primary" onClick={() => setCreateOpen(true)}>
          创建用户
        </Button>
      </Space>

      <Table
        columns={columns}
        dataSource={list}
        rowKey="id"
        loading={loading}
        onRow={(record: any) => ({
          onClick: () => showDetail(record.id),
          style: { cursor: 'pointer' },
        })}
        pagination={{
          current: page,
          pageSize: limit,
          total,
          onChange: (p) => setPage(p),
          showTotal: (t) => `共 ${t} 条`,
        }}
      />

      <Modal
        title="创建用户"
        open={createOpen}
        onOk={handleCreate}
        onCancel={() => setCreateOpen(false)}
        confirmLoading={createLoading}
      >
        <Form form={createForm} layout="vertical">
          <Form.Item
            name="email"
            label="邮箱"
            rules={[{ required: true, message: '请输入邮箱' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select options={ROLE_OPTIONS} />
          </Form.Item>
          <Form.Item name="referral_code" label="推荐码（选填）">
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="用户详情"
        open={detailId !== null}
        onClose={() => setDetailId(null)}
        width={400}
      >
        <Spin spinning={detailLoading}>
          {detail && (
            <div>
              <p><strong>ID：</strong>{detail.id}</p>
              <p><strong>邮箱：</strong>{detail.email}</p>
              <p><strong>角色：</strong>{ROLE_LABEL[detail.role] || detail.role}</p>
              <p><strong>额度：</strong>{detail.quota}</p>
              <p><strong>注册时间：</strong>{detail.created_at ? dayjs(detail.created_at).format('YYYY-MM-DD HH:mm') : '-'}</p>
            </div>
          )}
        </Spin>
      </Drawer>
    </PageContainer>
  );
}
