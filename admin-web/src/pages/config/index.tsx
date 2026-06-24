import { PageContainer } from '@ant-design/pro-components';
import { useRequest, request } from '@umijs/max';
import { Table, Button, Modal, Form, Input, Drawer, message } from 'antd';
import { useState } from 'react';
import dayjs from 'dayjs';

export default function ConfigPage() {
  const { data, loading, refresh } = useRequest(() =>
    request('/api/v1/admin/configs'),
  );

  const [editRecord, setEditRecord] = useState<any>(null);
  const [form] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);
  const [logsOpen, setLogsOpen] = useState(false);
  const [logs, setLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);

  const list = Array.isArray(data) ? data : data?.items || [];

  const handleEdit = async () => {
    const values = await form.validateFields();
    setEditLoading(true);
    try {
      await request(`/api/v1/admin/configs/${editRecord.key}`, {
        method: 'PUT',
        data: { config_value: values.config_value },
      });
      message.success('配置已更新');
      setEditRecord(null);
      form.resetFields();
      refresh();
    } catch {
      message.error('更新失败');
    } finally {
      setEditLoading(false);
    }
  };

  const showLogs = async () => {
    setLogsOpen(true);
    setLogsLoading(true);
    try {
      const res = await request('/api/v1/admin/config-change-logs');
      setLogs(Array.isArray(res) ? res : res?.items || []);
    } catch {
      message.error('获取变更日志失败');
    } finally {
      setLogsLoading(false);
    }
  };

  const columns = [
    { title: '配置项', dataIndex: 'key', width: 200 },
    { title: '值', dataIndex: 'config_value' },
    { title: '描述', dataIndex: 'description' },
    {
      title: '操作',
      width: 100,
      render: (_: any, record: any) => (
        <Button
          type="link"
          onClick={() => {
            setEditRecord(record);
            form.setFieldsValue({ config_value: record.config_value });
          }}
        >
          编辑
        </Button>
      ),
    },
  ];

  const logColumns = [
    { title: '配置项', dataIndex: 'key' },
    { title: '旧值', dataIndex: 'old_value' },
    { title: '新值', dataIndex: 'new_value' },
    { title: '操作人', dataIndex: 'operator' },
    {
      title: '时间',
      dataIndex: 'created_at',
      render: (t: string) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '-'),
    },
  ];

  return (
    <PageContainer>
      <div style={{ marginBottom: 16 }}>
        <Button onClick={showLogs}>变更日志</Button>
      </div>
      <Table
        columns={columns}
        dataSource={list}
        rowKey="key"
        loading={loading}
        pagination={false}
      />

      <Modal
        title="编辑配置"
        open={!!editRecord}
        onOk={handleEdit}
        onCancel={() => {
          setEditRecord(null);
          form.resetFields();
        }}
        confirmLoading={editLoading}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="config_value"
            label="配置值"
            rules={[{ required: true, message: '请输入配置值' }]}
          >
            <Input />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        title="变更日志"
        open={logsOpen}
        onClose={() => setLogsOpen(false)}
        width={700}
      >
        <Table
          columns={logColumns}
          dataSource={logs}
          rowKey="id"
          loading={logsLoading}
          pagination={{ pageSize: 20 }}
          size="small"
        />
      </Drawer>
    </PageContainer>
  );
}
