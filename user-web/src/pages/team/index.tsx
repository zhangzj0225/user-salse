import { Tabs, Table, Tag, Empty } from "antd";
import { useQuery } from "@tanstack/react-query";
import { teamApi } from "../../services/team";
import type { TeamMember, UpstreamMember } from "../../services/team";
import dayjs from "dayjs";

const roleLabelMap: Record<string, string> = {
  admin: "管理员",
  agent: "代理",
  distributor: "分销商",
  customer: "客户",
};

function formatRole(role: string) {
  return roleLabelMap[role] ?? role;
}

export default function TeamPage() {
  const { data: downstreamData, isLoading: downstreamLoading } = useQuery({
    queryKey: ["teamDownstream"],
    queryFn: () => teamApi.getDownstream(),
  });

  const { data: upstreamData, isLoading: upstreamLoading } = useQuery({
    queryKey: ["teamUpstream"],
    queryFn: () => teamApi.getUpstream(),
  });

  const downstreamColumns = [
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
    },
    {
      title: "昵称",
      dataIndex: "nickname",
      key: "nickname",
      render: (text: string) => text || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => <Tag color="blue">{formatRole(role)}</Tag>,
    },
    {
      title: "下级数量",
      dataIndex: "children_count",
      key: "children_count",
    },
    {
      title: "注册时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (text: string) => (text ? dayjs(text).format("YYYY-MM-DD HH:mm") : "-"),
    },
  ];

  const upstreamColumns = [
    {
      title: "邮箱",
      dataIndex: "email",
      key: "email",
    },
    {
      title: "昵称",
      dataIndex: "nickname",
      key: "nickname",
      render: (text: string) => text || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => <Tag color="blue">{formatRole(role)}</Tag>,
    },
  ];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>我的团队</h2>
      <Tabs
        items={[
          {
            key: "downstream",
            label: "下级团队",
            children: (
              <Table<TeamMember>
                columns={downstreamColumns}
                dataSource={downstreamData?.data ?? []}
                loading={downstreamLoading}
                rowKey="id"
                pagination={{ pageSize: 20, showSizeChanger: false }}
                locale={{
                  emptyText: <Empty description="暂无下级成员" />,
                }}
              />
            ),
          },
          {
            key: "upstream",
            label: "上级链路",
            children: (
              <Table<UpstreamMember>
                columns={upstreamColumns}
                dataSource={upstreamData?.data ?? []}
                loading={upstreamLoading}
                rowKey="id"
                pagination={false}
                locale={{
                  emptyText: <Empty description="暂无上级信息" />,
                }}
              />
            ),
          },
        ]}
      />
    </div>
  );
}
