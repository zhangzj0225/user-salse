import { useEffect, useState, useRef } from 'react';
import { Card, Input, Button, QRCode, Spin, Result, App } from 'antd';
import { CopyOutlined, ReloadOutlined } from '@ant-design/icons';
import type { AxiosError } from 'axios';
import { paymentApi } from '../services/api';

type PayStatus = 'idle' | 'pending' | 'success' | 'failed';

/** redirect 白名单 — 仅允许已知业务域名 */
const ALLOWED_REDIRECT_HOSTS = ['localhost', '127.0.0.1', 'sentiment.example.com'];

function isRedirectAllowed(url: string): boolean {
  try {
    const parsed = new URL(url, window.location.origin);
    return ALLOWED_REDIRECT_HOSTS.includes(parsed.hostname);
  } catch {
    return false;
  }
}

function PayPage() {
  const { message } = App.useApp();
  const [params] = useState(() => {
    const search = new URLSearchParams(window.location.search);
    return {
      amount: Number(search.get('amount')) || 0,
      referral: search.get('referral') || '',
      redirect: search.get('redirect') || '',
    };
  });

  const [email, setEmail] = useState('');
  const [referralCode, setReferralCode] = useState(params.referral);
  const [loading, setLoading] = useState(false);
  const [paymentId, setPaymentId] = useState<number | null>(null);
  const [status, setStatus] = useState<PayStatus>('idle');
  const [licenseCode, setLicenseCode] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [countdown, setCountdown] = useState(15 * 60);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  const handleCreateOrder = async () => {
    if (!email) {
      message.warning('请输入邮箱');
      return;
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      message.warning('请输入有效的邮箱地址');
      return;
    }
    if (!params.amount || params.amount <= 0) {
      message.error('支付金额无效');
      return;
    }
    setLoading(true);
    try {
      const res = await paymentApi.create({
        email,
        amount: params.amount,
        referral_code: referralCode || undefined,
        redirect_url: params.redirect || undefined,
      });
      setPaymentId(res.data.id);
      setStatus('pending');
      setCountdown(15 * 60);
    } catch (err: unknown) {
      const msg = (err as AxiosError<{ message?: string }>)?.response?.data?.message;
      message.error(msg || '创建订单失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (status !== 'pending' || !paymentId) return;

    const stopTimers = () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    };

    const poll = async () => {
      try {
        const res = await paymentApi.getStatus(paymentId);
        const data = res.data;
        if (data.status === 'success') {
          setStatus('success');
          setLicenseCode(data.license_code || '');
          stopTimers();
        } else if (data.status === 'failed') {
          setStatus('failed');
          setErrorMessage(data.message || '支付失败');
          stopTimers();
        }
      } catch {
        // 忽略轮询中的网络错误，等待下一次重试
      }
    };

    pollingRef.current = setInterval(poll, 3000);

    countdownRef.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          stopTimers();
          setStatus('failed');
          setErrorMessage('支付超时，请重新支付');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
    };
  }, [status, paymentId]);

  const handleCopy = () => {
    if (licenseCode) {
      navigator.clipboard.writeText(licenseCode).then(() => {
        message.success('License 已复制到剪贴板');
      });
    }
  };

  const handleRetry = () => {
    setStatus('idle');
    setPaymentId(null);
    setLicenseCode('');
    setErrorMessage('');
    setCountdown(15 * 60);
  };

  const handleReturn = () => {
    if (params.redirect && licenseCode && isRedirectAllowed(params.redirect)) {
      const separator = params.redirect.includes('?') ? '&' : '?';
      window.location.href = `${params.redirect}${separator}license=${encodeURIComponent(licenseCode)}`;
    }
  };

  return (
    <div style={{ maxWidth: 480, margin: '0 auto', padding: 16, minHeight: '100vh' }}>
      {status === 'idle' && (
        <Card title="支付订单" bordered>
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={{ fontSize: 14, color: '#888' }}>支付金额</div>
            <div style={{ fontSize: 40, fontWeight: 'bold', color: '#1677ff' }}>
              ¥{params.amount}
            </div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 8 }}>邮箱 *</div>
            <Input
              type="email"
              placeholder="请输入邮箱"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              size="large"
            />
          </div>
          <div style={{ marginBottom: 24 }}>
            <div style={{ marginBottom: 8 }}>推荐码（选填）</div>
            <Input
              placeholder="请输入推荐码"
              value={referralCode}
              onChange={(e) => setReferralCode(e.target.value)}
              size="large"
            />
          </div>
          <Button
            type="primary"
            block
            size="large"
            loading={loading}
            onClick={handleCreateOrder}
          >
            确认支付 ¥{params.amount}
          </Button>
        </Card>
      )}

      {status === 'pending' && (
        <Card title="扫码支付" bordered>
          <div style={{ textAlign: 'center' }}>
            <p style={{ color: '#888', marginBottom: 16 }}>请使用微信/支付宝扫码支付</p>
            <div style={{ display: 'inline-block', padding: 16, background: '#fff' }}>
              <QRCode value={`pay://${paymentId}`} size={200} />
            </div>
            <div style={{ fontSize: 28, fontWeight: 'bold', color: '#1677ff', margin: '16px 0 8px' }}>
              ¥{params.amount}
            </div>
            <div style={{ color: '#ff4d4f', marginBottom: 16 }}>
              剩余支付时间：{formatTime(countdown)}
            </div>
            <div>
              <Spin />
              <span style={{ marginLeft: 8, color: '#888' }}>等待支付确认...</span>
            </div>
          </div>
        </Card>
      )}

      {status === 'success' && (
        <Result
          status="success"
          title="支付成功"
          subTitle="License 已发送至您的邮箱"
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ marginBottom: 8, color: '#888' }}>License Code</div>
            <div style={{ fontSize: 20, fontWeight: 'bold', marginBottom: 16, wordBreak: 'break-all', padding: '0 16px' }}>
              {licenseCode}
            </div>
            <Button icon={<CopyOutlined />} onClick={handleCopy} style={{ marginBottom: 16 }}>
              复制 License
            </Button>
            <br />
            {params.redirect && (
              <Button type="primary" onClick={handleReturn}>
                返回业务系统
              </Button>
            )}
          </div>
        </Result>
      )}

      {status === 'failed' && (
        <Result
          status="error"
          title="支付失败"
          subTitle={errorMessage}
          extra={[
            <Button type="primary" key="retry" icon={<ReloadOutlined />} onClick={handleRetry}>
              重新支付
            </Button>,
          ]}
        />
      )}
    </div>
  );
}

export { PayPage };
