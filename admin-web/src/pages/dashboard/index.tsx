import { PageContainer } from '@ant-design/pro-components';
import { useRequest, request } from '@umijs/max';
import { Row, Col, Card, Statistic, Spin } from 'antd';

export default function DashboardPage() {
  const { data, loading } = useRequest(() =>
    request('/api/v1/admin/dashboard'),
  );

  const stats: any = data || {};

  const cards = [
    { title: '总用户数', value: stats.total_users },
    { title: '代理数', value: stats.agent_count },
    { title: '经销商数', value: stats.dealer_count },
    { title: '今日新增用户', value: stats.today_new_users },
    { title: '今日支付总额', value: stats.today_payment_total, prefix: '¥' },
    { title: '今日License生成数', value: stats.today_license_generated },
    { title: '今日License激活数', value: stats.today_license_activated },
    { title: '待处理工单数', value: stats.pending_tickets },
  ];

  return (
    <PageContainer>
      <Spin spinning={loading}>
        <Row gutter={[16, 16]}>
          {cards.map((card) => (
            <Col key={card.title} xs={24} sm={12} md={6}>
              <Card>
                <Statistic
                  title={card.title}
                  value={card.value ?? 0}
                  prefix={card.prefix}
                />
              </Card>
            </Col>
          ))}
        </Row>
      </Spin>
    </PageContainer>
  );
}
