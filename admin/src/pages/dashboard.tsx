import { BarChartOutlined, DatabaseOutlined, FileTextOutlined, SafetyCertificateOutlined, TeamOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Empty, Row, Space, Spin, Statistic, Tag, Typography } from "antd";
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

type T0Status = {
  running: boolean;
  connected: boolean;
  phase: string;
  lastMessageAt: string | null;
  lastSnapshotAt: string | null;
  lastError: string | null;
  ssiForeignPhase?: string | null;
  lastForeignSyncAt?: string | null;
  updatedAt: string | null;
};

type HistorySyncStatus = {
  running: boolean;
  mode: "RESET" | "INCREMENTAL";
  phase: string;
  error: string | null;
};

type StockSyncStatus = {
  running: boolean;
  phase: string;
  error: string | null;
};

type FinanceChartSyncStatus = {
  status: string;
  mode: string;
  processedCount: number;
  eligibleCount: number;
  lastError: string | null;
};

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("vi-VN");
}

function renderHealthTag(kind: "success" | "warning" | "error" | "default", text: string) {
  const colorByKind = {
    success: "green",
    warning: "gold",
    error: "red",
    default: "default",
  } as const;

  return <Tag color={colorByKind[kind]}>{text}</Tag>;
}

export function DashboardPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [workerLoading, setWorkerLoading] = useState(false);
  const [t0Status, setT0Status] = useState<T0Status | null>(null);
  const [historyStatus, setHistoryStatus] = useState<HistorySyncStatus | null>(null);
  const [stockSyncStatus, setStockSyncStatus] = useState<StockSyncStatus | null>(null);
  const [financeChartStatus, setFinanceChartStatus] = useState<FinanceChartSyncStatus | null>(null);

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

  async function loadWorkerHealth() {
    setWorkerLoading(true);
    try {
      const [t0Res, historyRes, stockSyncRes, financeRes] = await Promise.all([
        apiClient.get<ApiEnvelope<T0Status>>("/admin/stocks/t0-status"),
        apiClient.get<ApiEnvelope<HistorySyncStatus>>("/admin/stocks/history/sync/status"),
        apiClient.get<ApiEnvelope<StockSyncStatus>>("/admin/stocks/sync/status"),
        apiClient.get<ApiEnvelope<FinanceChartSyncStatus>>("/admin/stock-finance-charts/sync/status"),
      ]);
      setT0Status(t0Res.data.data);
      setHistoryStatus(historyRes.data.data);
      setStockSyncStatus(stockSyncRes.data.data);
      setFinanceChartStatus(financeRes.data.data);
    } finally {
      setWorkerLoading(false);
    }
  }

  useEffect(() => {
    void load();
    void loadWorkerHealth();
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

      <Card
        title="Worker Health"
        extra={<Button onClick={() => void loadWorkerHealth()} loading={workerLoading}>Lam moi</Button>}
      >
        <Row gutter={[16, 16]}>
          <Col xs={24} md={12}>
            <Card size="small" title="T0 Stream">
              <Space wrap>
                {t0Status?.running && t0Status?.connected
                  ? renderHealthTag("success", "Dang chay")
                  : t0Status?.running
                    ? renderHealthTag("warning", "Dang chay nhung mat ket noi")
                    : renderHealthTag("error", "Khong chay")}
                {renderHealthTag("default", t0Status?.phase ?? "-")}
              </Space>
              <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 6 }}>
                Message cuoi: {formatDateTime(t0Status?.lastMessageAt)}
              </Typography.Paragraph>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 6 }}>
                Snapshot cuoi: {formatDateTime(t0Status?.lastSnapshotAt)}
              </Typography.Paragraph>
              <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
                Updated: {formatDateTime(t0Status?.updatedAt)}
              </Typography.Paragraph>
              {t0Status?.lastError ? <Alert style={{ marginTop: 12 }} type="warning" showIcon message={t0Status.lastError} /> : null}
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Card size="small" title="T0 Foreign Sync">
              <Space wrap>
                {t0Status?.ssiForeignPhase?.toLowerCase().includes("loi")
                  ? renderHealthTag("error", "Can xu ly")
                  : renderHealthTag("success", t0Status?.ssiForeignPhase ?? "Khong ro")}
              </Space>
              <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                Lan sync cuoi: {formatDateTime(t0Status?.lastForeignSyncAt)}
              </Typography.Paragraph>
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Card size="small" title="History Sync">
              <Space wrap>
                {historyStatus?.running
                  ? renderHealthTag("warning", `Dang chay ${historyStatus.mode}`)
                  : renderHealthTag("default", "Idle")}
                {renderHealthTag("default", historyStatus?.phase ?? "-")}
              </Space>
              {historyStatus?.error ? <Alert style={{ marginTop: 12 }} type="error" showIcon message={historyStatus.error} /> : null}
            </Card>
          </Col>

          <Col xs={24} md={12}>
            <Card size="small" title="Finance Chart Sync">
              <Space wrap>
                {financeChartStatus?.status === "RUNNING" || financeChartStatus?.status === "PENDING"
                  ? renderHealthTag("warning", financeChartStatus.status)
                  : financeChartStatus?.status === "INTERRUPTED" || financeChartStatus?.status === "FAILED"
                    ? renderHealthTag("error", financeChartStatus.status)
                    : renderHealthTag("default", financeChartStatus?.status ?? "Unknown")}
                {financeChartStatus
                  ? renderHealthTag("default", `${financeChartStatus.processedCount}/${financeChartStatus.eligibleCount}`)
                  : null}
              </Space>
              <Typography.Paragraph type="secondary" style={{ marginTop: 12, marginBottom: 0 }}>
                Mode: {financeChartStatus?.mode ?? "-"}
              </Typography.Paragraph>
              {financeChartStatus?.lastError && financeChartStatus.lastError !== "Recovered after application restart"
                ? <Alert style={{ marginTop: 12 }} type="error" showIcon message={financeChartStatus.lastError} />
                : null}
            </Card>
          </Col>

          <Col xs={24}>
            <Card size="small" title="Stock Symbol Sync">
              <Space wrap>
                {stockSyncStatus?.running
                  ? renderHealthTag("warning", "Dang sync")
                  : renderHealthTag("default", "Idle")}
                {renderHealthTag("default", stockSyncStatus?.phase ?? "-")}
              </Space>
              {stockSyncStatus?.error ? <Alert style={{ marginTop: 12 }} type="error" showIcon message={stockSyncStatus.error} /> : null}
            </Card>
          </Col>
        </Row>
      </Card>

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
