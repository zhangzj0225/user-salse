import { Tabs, Table, Tag, Empty } from "antd";
import { useQuery } from "@tanstack/react-query";
import { teamApi } from "../../services/team";
import type { TeamMember, UpstreamMember } from "../../services/team";
import dayjs from "dayjs";

const roleLabelMap: Record<string, string> = {
  distributor: "经销商",
  agent: "代理",
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

  // 后端返回 {total_count, root:{children:[...]}}，取 root.children 为直接下级
  const downstreamColumns = [
    {
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
    },
    {
      title: "昵称",
      dataIndex: "nickname",
      key: "nickname",
      render: (text: string | null) => text || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => <Tag color="blue">{formatRole(role)}</Tag>,
    },
    {
      title: "下级数量",
      dataIndex: "direct_downline_count",
      key: "direct_downline_count",
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
      title: "用户ID",
      dataIndex: "user_id",
      key: "user_id",
    },
    {
      title: "昵称",
      dataIndex: "nickname",
      key: "nickname",
      render: (text: string | null) => text || "-",
    },
    {
      title: "角色",
      dataIndex: "role",
      key: "role",
      render: (role: string) => <Tag color="blue">{formatRole(role)}</Tag>,
    },
    {
      title: "层级",
      dataIndex: "level",
      key: "level",
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
                dataSource={downstreamData?.root?.children ?? []}
                loading={downstreamLoading}
                rowKey="user_id"
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
                dataSource={upstreamData?.chain ?? []}
                loading={upstreamLoading}
                rowKey="user_id"
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
