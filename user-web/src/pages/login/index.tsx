import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Card, Form, Input, Button, App as AntdApp } from "antd";
import { authApi } from "../../services/auth";
import { useAuthStore } from "../../stores/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const { message } = AntdApp.useApp();
  const setAuth = useAuthStore((s) => s.setAuth);
  const token = useAuthStore((s) => s.token);
  const [loginForm] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [loginCountdown, setLoginCountdown] = useState(0);
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

  const startCountdown = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
    setLoginCountdown(60);
    const timer = setInterval(() => {
      setLoginCountdown((c) => {
        if (c <= 1) {
          clearInterval(timer);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    timerRef.current = timer;
  };

  const handleSendCode = async (email: string) => {
    if (!email) {
      message.warning("请输入邮箱");
      return;
    }
    // 已在倒计时中或正在发送，防止重复
    if (loginCountdown > 0 || sending) return;
    setSending(true);
    try {
      await authApi.sendEmailCode({ email, scene: "login" });
      message.success("验证码已发送");
      startCountdown();
    } catch {
      // 错误已由拦截器处理
    } finally {
      setSending(false);
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
        <h2 style={{ textAlign: "center", marginBottom: 24 }}>用户分销系统</h2>
        <Form form={loginForm} onFinish={handleLogin} layout="vertical">
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: "请输入邮箱" },
              { type: "email", message: "邮箱格式不正确" },
            ]}
          >
            <Input placeholder="请输入邮箱" autoComplete="email" />
          </Form.Item>
          <Form.Item
            name="code"
            label="验证码"
            rules={[
              { required: true, message: "请输入验证码" },
              {
                pattern: /^\d{6}$/,
                message: "验证码为 6 位数字",
              },
            ]}
          >
            <Input.Search
              placeholder="请输入验证码"
              maxLength={6}
              enterButton={loginCountdown > 0 ? `${loginCountdown}s` : "获取验证码"}
              disabled={sending}
              loading={sending && loginCountdown === 0}
              onSearch={() => handleSendCode(loginForm.getFieldValue("email"))}
            />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            登录
          </Button>
        </Form>
      </Card>
    </div>
  );
}
