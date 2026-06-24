import axios from 'axios';

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
});

// 响应拦截器：解包后端统一包装 { data: {...} }
// 后端所有成功响应格式为 { data: <业务数据> }，前端只需业务数据。
instance.interceptors.response.use((res) => {
  if (res.data && typeof res.data === 'object' && 'data' in res.data) {
    return { ...res, data: res.data.data };
  }
  return res;
});

export const paymentApi = {
  create(data: { email: string; amount: number; referral_code?: string; redirect_url?: string }) {
    return instance.post('/payments/create', data);
  },
  getStatus(paymentId: number) {
    return instance.get(`/payments/${paymentId}/status`);
  },
};
