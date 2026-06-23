import axios from 'axios';

const instance = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
});

export const paymentApi = {
  create(data: { email: string; amount: number; referral_code?: string; redirect_url?: string }) {
    return instance.post('/payments/create', data);
  },
  getStatus(paymentId: number) {
    return instance.get(`/payments/${paymentId}/status`);
  },
};
