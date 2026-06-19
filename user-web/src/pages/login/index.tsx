import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Form, Input, Button, Tabs, App as AntdApp } from "antd";
import { authApi } from "../../services/auth";
import { useAuthStore } from "../../stores/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const setAuth = useAuthStore((s) => s.setAuth);
  const token = useAuthStore((s) => s.token);
  const [loginForm] = Form.useForm();
  const [registerForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [loginCountdown, setLoginCountdown] = useState(0);
  const [registerCountdown, setRegisterCountdown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // 已登录用户重定向到首页
  useEffect(() => {
    if (token) {
      navigate("/", { replace: true });
    }
  }, [token, navigate]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const startCountdown = (
    setter: React.Dispatch<React.SetStateAction<number>>,
  ) => {
    setter(60);
    const timer = setInterval(() => {
      setter((c) => {
        if (c <= 1) {
          clearInterval(timer);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    timerRef.current = timer;
  };

  const handleSendCode = async (
    email: string,
    scene: "login" | "register",
    setter: React.Dispatch<React.SetStateAction<number>>,
  ) => {
    if (!email) {
      message.warning("请输入邮箱");
      return;
    }
    try {
      await authApi.sendEmailCode({ email, scene });
      message.success("验证码已发送");
      startCountdown(setter);
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
                <Form form={loginForm} onFinish={handleLogin} layout="vertical">
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
                        loginCountdown > 0
                          ? `${loginCountdown}s`
                          : "获取验证码"
                      }
                      disabled={loginCountdown > 0}
                      onSearch={() =>
                        handleSendCode(
                          loginForm.getFieldValue("email"),
                          "login",
                          setLoginCountdown,
                        )
                      }
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
                <Form
                  form={registerForm}
                  onFinish={handleRegister}
                  layout="vertical"
                >
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
                        registerCountdown > 0
                          ? `${registerCountdown}s`
                          : "获取验证码"
                      }
                      disabled={registerCountdown > 0}
                      onSearch={() =>
                        handleSendCode(
                          registerForm.getFieldValue("email"),
                          "register",
                          setRegisterCountdown,
                        )
                      }
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
