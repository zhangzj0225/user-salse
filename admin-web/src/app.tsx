import { RequestConfig } from '@umijs/max';

export const request: RequestConfig = {
  timeout: 10000,
  errorConfig: {
    errorThrower: (res) => {
      // Throw error for non-200 responses
    },
    errorHandler: (error: any) => {
      // Global error handling
    },
  },
  requestInterceptors: [
    (url, options) => {
      const token = localStorage.getItem('token');
      if (token) {
        return {
          url,
          options: {
            ...options,
            headers: {
              ...options.headers,
              Authorization: `Bearer ${token}`,
            },
          },
        };
      }
      return { url, options };
    },
  ],
};

export async function getInitialState() {
  const token = localStorage.getItem('token');
  return {
    currentUser: token ? { name: 'Admin' } : undefined,
  };
}
