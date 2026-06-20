import { useState } from "react";
import { Layout, Menu, Button, Avatar, Space, Typography, Badge } from "antd";
import type { MenuProps } from "antd";
import {
  HomeOutlined,
  TeamOutlined,
  DollarOutlined,
  WalletOutlined,
  ShoppingOutlined,
  MoneyCollectOutlined,
  UserOutlined,
  BellOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from "@ant-design/icons";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../stores/auth";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const roleLabelMap: Record<string, string> = {
  user: "普通用户",
  member: "888会员",
  distributor: "经销商",
  agent: "代理",
};

export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [collapsed, setCollapsed] = useState(false);

  const canSales = user?.role === "agent" || user?.role === "distributor";

  const menuItems: MenuProps["items"] = [
    { key: "/", icon: <HomeOutlined />, label: "首页" },
    { key: "/team", icon: <TeamOutlined />, label: "我的团队" },
    { key: "/earnings", icon: <DollarOutlined />, label: "我的收益" },
    { key: "/recharge", icon: <WalletOutlined />, label: "充值" },
    ...(canSales ? [{ key: "/sales", icon: <ShoppingOutlined />, label: "销售账号" }] : []),
    { key: "/withdrawal", icon: <MoneyCollectOutlined />, label: "提现" },
    { key: "/profile", icon: <UserOutlined />, label: "我的" },
  ];

  const handleMenuClick: MenuProps["onClick"] = ({ key }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider trigger={null} collapsible collapsed={collapsed} theme="dark" width={220}>
        <div
          style={{
            height: 56,
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: 600,
            fontSize: 16,
            whiteSpace: "nowrap",
            overflow: "hidden",
          }}
        >
          {collapsed ? "分销" : "足球舆情分销系统"}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            boxShadow: "0 1px 4px rgba(0,21,41,0.08)",
          }}
        >
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
          <Space size="large" align="center">
            <Badge dot offset={[-2, 4]}>
              <Button
                type="text"
                icon={<BellOutlined style={{ fontSize: 18 }} />}
                onClick={() => navigate("/notifications")}
              />
            </Badge>
            <Space align="center">
              <Avatar icon={<UserOutlined />} />
              <Text>{user?.nickname || user?.email}</Text>
              <Text type="secondary">({roleLabelMap[user?.role ?? ""] ?? user?.role})</Text>
            </Space>
            <Button type="text" danger icon={<LogoutOutlined />} onClick={handleLogout}>
              退出登录
            </Button>
          </Space>
        </Header>
        <Content
          style={{
            margin: 16,
            padding: 24,
            background: "#fff",
            borderRadius: 8,
            minHeight: 280,
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
