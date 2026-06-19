import { useEffect } from "react";
import { App as AntdApp } from "antd";
import { AppRouter } from "./router";
import { setErrorHandler } from "./services/api";

export default function App() {
  const { message } = AntdApp.useApp();

  // 注入 antd message 实例到 API 错误处理器
  useEffect(() => {
    setErrorHandler((msg) => message.error(msg));
  }, [message]);

  return <AppRouter />;
}
