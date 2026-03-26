import { BarChartOutlined, DatabaseOutlined, FileTextOutlined, SafetyCertificateOutlined, TeamOutlined } from "@ant-design/icons";
import { Button, Card, Col, Empty, Row, Space, Spin, Statistic, Typography } from "antd";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiClient, type ApiEnvelope } from "../lib/api";

type DashboardStats = {
  stocks: number;
  posts: number;
  categories: number;
  users: number;
  roles: number;
};

type StockPage = {
  totalElements: number;
};

type BasicItem = { id: number };

export function DashboardPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<DashboardStats | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [stocksRes, postsRes, categoriesRes, usersRes, rolesRes] = await Promise.all([
        apiClient.get<ApiEnvelope<StockPage>>("/admin/stocks", { params: { page: 0, size: 1 } }),
        apiClient.get<ApiEnvelope<BasicItem[]>>("/admin/posts"),
        apiClient.get<ApiEnvelope<BasicItem[]>>("/admin/categories"),
        apiClient.get<ApiEnvelope<BasicItem[]>>("/admin/users"),
        apiClient.get<ApiEnvelope<BasicItem[]>>("/admin/rbac/roles"),
      ]);
      setStats({
        stocks: stocksRes.data.data.totalElements ?? 0,
        posts: postsRes.data.data.length,
        categories: categoriesRes.data.data.length,
        users: usersRes.data.data.length,
        roles: rolesRes.data.data.length,
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (loading && !stats) {
    return (
      <div style={{ minHeight: 260, display: "grid", placeItems: "center" }}>
        <Spin />
      </div>
    );
  }

  if (!stats) {
    return <Empty description="Khong tai duoc dashboard" />;
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3} style={{ margin: 0 }}>
        Dashboard
      </Typography.Title>
      <Typography.Text type="secondary">
        Tong quan nhanh ve du lieu va cac khu vuc quan tri.
      </Typography.Text>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <Statistic title="Stocks" value={stats.stocks} prefix={<DatabaseOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <Statistic title="Posts" value={stats.posts} prefix={<FileTextOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <Statistic title="Categories" value={stats.categories} prefix={<BarChartOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <Statistic title="Users" value={stats.users} prefix={<TeamOutlined />} />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={8}>
          <Card>
            <Statistic title="Roles" value={stats.roles} prefix={<SafetyCertificateOutlined />} />
          </Card>
        </Col>
      </Row>

      <Card title="Quick Actions">
        <Space wrap>
          <Button type="primary" onClick={() => navigate("/sync-data")}>
            Sync du lieu
          </Button>
          <Button onClick={() => navigate("/analytics")}>Mo Analytics</Button>
          <Button onClick={() => navigate("/stocks")}>Quan ly Stocks</Button>
          <Button onClick={() => navigate("/posts")}>Quan ly Posts</Button>
          <Button onClick={() => navigate("/users")}>Quan ly Users</Button>
        </Space>
      </Card>
    </Space>
  );
}
