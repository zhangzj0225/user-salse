import { Button, Space, Typography } from "antd";
import { useAuthStore } from "../../stores/auth";
import { useNavigate } from "react-router-dom";

const { Title, Text } = Typography;

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ padding: 24 }}>
      <Space direction="vertical" size="large">
        <Title level={2}>首页</Title>
        <div>
          <Text>欢迎，{user?.email}</Text>
          <br />
          <Text type="secondary">角色：{user?.role}</Text>
        </div>
        <Button onClick={handleLogout}>退出登录</Button>
      </Space>
    </div>
  );
}
