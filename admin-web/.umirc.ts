import { defineConfig } from '@umijs/max';

export default defineConfig({
  antd: {},
  access: {},
  model: {},
  initialState: {},
  request: {},
  layout: {
    title: '足球舆情分销管理',
  },
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      name: '数据看板',
      path: '/dashboard',
      component: './dashboard',
    },
    {
      name: '用户管理',
      path: '/users',
      component: './users',
    },
    {
      name: '准入审核',
      path: '/approvals',
      component: './approvals',
    },
    {
      name: '工单管理',
      path: '/tickets',
      component: './tickets',
    },
    {
      name: '系统配置',
      path: '/config',
      component: './config',
    },
  ],
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
  npmClient: 'npm',
});
