import axios, { type AxiosError } from "axios";
import { useAuthStore } from "../stores/auth";

const instance = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
});

// 请求拦截器：附加 JWT
instance.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 错误消息提取
function extractErrorMessage(error: AxiosError): string {
  const data = error.response?.data as { detail?: unknown } | undefined;
  const detail = data?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  // FastAPI 422 校验错误：detail 是数组 [{loc, msg, type}]
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string };
    return first.msg ?? "参数校验失败";
  }
  if (!error.response) {
    return "网络异常，请稍后重试";
  }
  return `请求失败 (${error.response.status})`;
}

// 外部设置的错误回调，由 App 组件注入 antd message 实例
let errorHandler: ((msg: string) => void) | null = null;

export function setErrorHandler(fn: (msg: string) => void) {
  errorHandler = fn;
}

// 响应拦截器：统一错误处理。成功时返回 response.data（HTTP body），
// 调用方通过 request<T> 拿到强类型 body。
instance.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    const msg = extractErrorMessage(error);
    if (errorHandler) {
      errorHandler(msg);
    } else {
      // errorHandler 注入前的窗口（首渲前请求失败）：至少落控制台，避免静默吞错
      console.error("[api] 未捕获的错误:", msg, error);
    }
    if (error.response?.status === 401) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);

/**
 * Typed request helper。
 *
 * 后端统一响应体为 `{ data: T }`（见 backend/app/api/v1 各端点 return {"data": ...}）。
 * 响应拦截器已解包 axios 的 AxiosResponse，返回的是 HTTP body（即 `{ data: T }`）。
 * 因此这里 T 应声明为完整的 body 形状（含外层 data），调用方再解构 `res.data` 取业务数据。
 */
export function request<T>(config: Parameters<typeof instance.request>[0]): Promise<T> {
  return instance.request<T, T>(config);
}

export default instance;
