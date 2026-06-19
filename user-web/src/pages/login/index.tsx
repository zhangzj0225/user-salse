import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Form, Input, Button, Tabs, message } from "antd";
import { authApi } from "../../services/auth";
import { useAuthStore } from "../../stores/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [loading, setLoading] = useState(false);
  const [countdown, setCountdown] = useState(0);

  const handleSendCode = async (email: string, scene: "login" | "register") => {
    if (!email) {
      message.warning("请输入邮箱");
      return;
    }
    try {
      await authApi.sendEmailCode({ email, scene });
      message.success("验证码已发送");
      setCountdown(60);
      const timer = setInterval(() => {
        setCountdown((c) => {
          if (c <= 1) {
            clearInterval(timer);
            return 0;
          }
          return c - 1;
        });
      }, 1000);
    } catch {
      // 错误已由拦截器处理
    }
  };

  const handleLogin = async (values: { email: string; code: string }) => {
    setLoading(true);
    try {
      const res = await authApi.login(values);
      const { token, user } = res.data;
      setAuth(token, user);
      navigate("/");
    } catch {
      // 错误已由拦截器处理
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: {
    email: string;
    code: string;
    invite_code: string;
  }) => {
    setLoading(true);
    try {
      const res = await authApi.register(values);
      const { token, user } = res.data;
      setAuth(token, user);
      navigate("/");
    } catch {
      // 错误已由拦截器处理
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#f0f2f5",
      }}
    >
      <Card style={{ width: 420 }}>
        <h2 style={{ textAlign: "center", marginBottom: 24 }}>
          足球舆情分销系统
        </h2>
        <Tabs
          items={[
            {
              key: "login",
              label: "登录",
              children: (
                <Form onFinish={handleLogin} layout="vertical">
                  <Form.Item
                    name="email"
                    label="邮箱"
                    rules={[{ required: true, message: "请输入邮箱" }]}
                  >
                    <Input placeholder="请输入邮箱" />
                  </Form.Item>
                  <Form.Item
                    name="code"
                    label="验证码"
                    rules={[{ required: true, message: "请输入验证码" }]}
                  >
                    <Input.Search
                      placeholder="请输入验证码"
                      enterButton={
                        countdown > 0 ? `${countdown}s` : "获取验证码"
                      }
                      onSearch={(val) => handleSendCode(val, "login")}
                    />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading}
                  >
                    登录
                  </Button>
                </Form>
              ),
            },
            {
              key: "register",
              label: "注册",
              children: (
                <Form onFinish={handleRegister} layout="vertical">
                  <Form.Item
                    name="email"
                    label="邮箱"
                    rules={[{ required: true, message: "请输入邮箱" }]}
                  >
                    <Input placeholder="请输入邮箱" />
                  </Form.Item>
                  <Form.Item
                    name="code"
                    label="验证码"
                    rules={[{ required: true, message: "请输入验证码" }]}
                  >
                    <Input.Search
                      placeholder="请输入验证码"
                      enterButton={
                        countdown > 0 ? `${countdown}s` : "获取验证码"
                      }
                      onSearch={(val) => handleSendCode(val, "register")}
                    />
                  </Form.Item>
                  <Form.Item
                    name="invite_code"
                    label="邀请码"
                    rules={[{ required: true, message: "请输入邀请码" }]}
                  >
                    <Input placeholder="请输入邀请码" />
                  </Form.Item>
                  <Button
                    type="primary"
                    htmlType="submit"
                    block
                    loading={loading}
                  >
                    注册
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
