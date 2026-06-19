import axios from "axios";
import { message } from "antd";
import { useAuthStore } from "../stores/auth";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
});

// 请求拦截器：附加 JWT
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器：统一错误处理
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail;
    if (detail) {
      message.error(detail);
    }
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

export default api;
