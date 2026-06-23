import React from 'react';
import ReactDOM from 'react-dom/client';
import { ConfigProvider, App } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import RootApp from './App';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <App>
        <RootApp />
      </App>
    </ConfigProvider>
  </React.StrictMode>
);
