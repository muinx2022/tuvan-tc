import { Link, useSearchParams } from "react-router-dom";
import { Alert, Button, Card, Descriptions, Grid, Input, Space, Table, Tag, Typography, message } from "antd";
import { EditOutlined, EyeOutlined, LoadingOutlined, ReloadOutlined, SyncOutlined } from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type StockFinanceChartTickerItem = {
  stockSymbolId: number;
  ticker: string;
  chartCount: number;
  reportTypes: string[];
  lastSyncedAt: string | null;
};

type StockFinanceChartTickerPage = {
  items: StockFinanceChartTickerItem[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

type StockFinanceChartSyncStatus = {
  jobId: number | null;
  mode: string;
  status: string;
  batchNo: number;
  batchSize: number;
  eligibleCount: number;
  processedCount: number;
  successCount: number;
  failedCount: number;
  skippedCount: number;
  totalEligibleCount: number;
  existingCount: number;
  startedAt: string | null;
  finishedAt: string | null;
  lastError: string | null;
};

type StockFinanceChartSyncStartResponse = {
  jobId: number;
  mode: string;
  status: string;
  batchSize: number;
  eligibleCount: number;
};

type HistorySyncStatus = {
  running: boolean;
  mode: "RESET" | "INCREMENTAL";
  days: number;
  totalSymbols: number;
  processedSymbols: number;
  failedSymbols: number;
  recordsUpdated: number;
  phase: string;
  error: string | null;
};

export function StockFinanceChartsPage() {
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.md;
  const [searchParams, setSearchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);

  const currentPage = Math.max(0, Number(searchParams.get("page") ?? 0));
  const currentSize = Number(searchParams.get("size") ?? 20);
  const [tickerFilter, setTickerFilter] = useState(searchParams.get("ticker") ?? "");

  const [data, setData] = useState<StockFinanceChartTickerPage>({
    items: [],
    page: currentPage,
    size: currentSize,
    totalElements: 0,
    totalPages: 0,
  });
  const [status, setStatus] = useState<StockFinanceChartSyncStatus | null>(null);
  const [historyStatus, setHistoryStatus] = useState<HistorySyncStatus | null>(null);
  const statusRequestInFlightRef = useRef(false);

  function updateSearchParams(page: number, size: number, ticker: string) {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("page", String(page));
        next.set("size", String(size));
        if (ticker.trim()) {
          next.set("ticker", ticker.trim());
        } else {
          next.delete("ticker");
        }
        return next;
      },
      { replace: true },
    );
  }

  async function loadTickers(page = currentPage, size = currentSize, ticker = tickerFilter, silent = false) {
    if (!silent) {
      setLoading(true);
    }
    try {
      const res = await apiClient.get<ApiEnvelope<StockFinanceChartTickerPage>>("/admin/stock-finance-charts/tickers", {
        params: { page, size, ticker: ticker.trim() || undefined },
      });
      setData({
        ...res.data.data,
        items: [...res.data.data.items].sort((left, right) => left.ticker.localeCompare(right.ticker, "en", { sensitivity: "base" })),
      });
      updateSearchParams(page, size, ticker);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }

  async function loadStatus(silent = false) {
    if (statusRequestInFlightRef.current) {
      return;
    }
    statusRequestInFlightRef.current = true;
    if (!silent) {
      setStatusLoading(true);
    }
    try {
      const [chartRes, historyRes] = await Promise.all([
        apiClient.get<ApiEnvelope<StockFinanceChartSyncStatus>>("/admin/stock-finance-charts/sync/status"),
        apiClient.get<ApiEnvelope<HistorySyncStatus>>("/admin/stocks/history/sync/status"),
      ]);
      setStatus(chartRes.data.data);
      setHistoryStatus(historyRes.data.data);
    } finally {
      statusRequestInFlightRef.current = false;
      if (!silent) {
        setStatusLoading(false);
      }
    }
  }

  async function startSync(mode: "missing" | "reset") {
    if (mode === "missing") {
      setStarting(true);
    } else {
      setResetting(true);
    }
    try {
      const res = await apiClient.post<ApiEnvelope<StockFinanceChartSyncStartResponse>>(
        "/admin/stock-finance-charts/sync/start",
        null,
        { params: { mode } },
      );
      if (res.data.data.eligibleCount === 0 && mode === "missing") {
        message.info("Khong con ma nao thieu du lieu de sync.");
      } else {
        message.success(
          mode === "reset"
            ? `Da reset va bat dau sync job #${res.data.data.jobId} (${res.data.data.eligibleCount} ma)`
            : `Da bat dau sync ma chua co du lieu #${res.data.data.jobId} (${res.data.data.eligibleCount} ma)`,
        );
      }
      await Promise.all([loadStatus(true), loadTickers(currentPage, currentSize, tickerFilter, true)]);
    } finally {
      setStarting(false);
      setResetting(false);
    }
  }

  useEffect(() => {
    void loadTickers(currentPage, currentSize, tickerFilter);
    void loadStatus();
  }, []);

  const historyRunning = historyStatus?.running ?? false;
  const chartRunning = status?.status === "RUNNING" || status?.status === "PENDING";
  const hasInterruptedJob = status?.status === "INTERRUPTED";
  const noMissingTicker =
    !tickerFilter.trim() &&
    (status?.eligibleCount ?? 0) > 0 &&
    data.totalElements >= (status?.eligibleCount ?? 0) &&
    !hasInterruptedJob;

  useEffect(() => {
    if (!chartRunning) {
      return;
    }
    const intervalId = window.setInterval(() => {
      void Promise.all([loadStatus(true), loadTickers(data.page, data.size, tickerFilter, true)]);
    }, 10000);
    return () => window.clearInterval(intervalId);
  }, [chartRunning, data.page, data.size, tickerFilter]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large" className="finance-charts-page">
      <Typography.Title level={3}>Vietstock Finance Charts</Typography.Title>
      <Card loading={statusLoading} className="finance-charts-status-card">
        <Space wrap style={{ width: "100%", justifyContent: "space-between" }} className="finance-charts-status-wrap">
          <Descriptions size="small" column={isMobile ? 1 : 3} className="finance-charts-status-descriptions">
            <Descriptions.Item label="Trang thai">
              <Tag color={status?.status === "RUNNING" ? "processing" : status?.status === "FAILED" ? "error" : "default"}>
                <Space size={6}>
                  {chartRunning ? <LoadingOutlined spin /> : null}
                  <span>{status?.status ?? "IDLE"}</span>
                </Space>
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Che do">
              {status?.mode === "RESET_AND_SYNC" ? "Reset + sync lai" : "Sync ma chua co du lieu"}
            </Descriptions.Item>
            <Descriptions.Item label="Tong ma can sync">{status?.eligibleCount ?? 0}</Descriptions.Item>
            <Descriptions.Item label="Da co du lieu">
              {status?.existingCount ?? 0}/{status?.totalEligibleCount ?? 0}
            </Descriptions.Item>
            <Descriptions.Item label="Success">{status?.successCount ?? 0}</Descriptions.Item>
            <Descriptions.Item label="Failed">{status?.failedCount ?? 0}</Descriptions.Item>
            <Descriptions.Item label="Tien do" span={2}>
              {(status?.processedCount ?? 0) + (status?.failedCount ?? 0)}/{status?.eligibleCount ?? 0}
            </Descriptions.Item>
            <Descriptions.Item label="History sync" span={2}>
              {historyRunning ? `Dang chay (${historyStatus?.mode ?? "INCREMENTAL"} | ${historyStatus?.phase ?? "..."})` : "Khong chay"}
            </Descriptions.Item>
          </Descriptions>
          <Space className="finance-charts-status-actions">
            <Button
              type="primary"
              icon={<SyncOutlined />}
              onClick={() => void startSync("missing")}
              loading={starting}
              disabled={historyRunning || chartRunning || noMissingTicker}
            >
              Sync ma chua co du lieu
            </Button>
            <Button
              danger
              icon={<SyncOutlined />}
              onClick={() => void startSync("reset")}
              loading={resetting}
              disabled={historyRunning || chartRunning}
            >
              Reset + sync lai
            </Button>
          </Space>
        </Space>
        {status?.lastError && status.lastError !== "Recovered after application restart" ? (
          <Alert
            type="error"
            showIcon
            style={{ marginTop: 12 }}
            message={status.lastError}
          />
        ) : null}
      </Card>

      <Card className="finance-charts-table-card">
        <Space wrap style={{ marginBottom: 12 }} className="finance-charts-filters">
          <Input
            placeholder="Loc theo ticker"
            value={tickerFilter}
            onChange={(event) => setTickerFilter(event.target.value)}
            onPressEnter={() => void loadTickers(0, data.size, tickerFilter)}
            className="finance-charts-filter-input"
            style={{ width: isMobile ? "100%" : 220 }}
          />
          <Button type="primary" onClick={() => void loadTickers(0, data.size, tickerFilter)}>
            Tim
          </Button>
          <Button
            onClick={() => {
              setTickerFilter("");
              void loadTickers(0, data.size, "");
            }}
          >
            Bo loc
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => void loadTickers()} loading={loading}>
            Refresh danh sach
          </Button>
        </Space>

        <Table<StockFinanceChartTickerItem>
          className="finance-charts-table"
          rowKey={(record) => record.ticker}
          loading={loading}
          dataSource={data.items}
          columns={[
            {
              title: "Ticker",
              dataIndex: "ticker",
              render: (value: string) => <Link to={`/stock-finance-charts/${value}`}>{value}</Link>,
            },
            { title: "Stock ID", dataIndex: "stockSymbolId" },
            { title: "So chart", dataIndex: "chartCount" },
            {
              title: "Loai bao cao",
              dataIndex: "reportTypes",
              render: (values: string[]) => (
                <Space wrap>{values.map((value) => <Tag key={value}>{value}</Tag>)}</Space>
              ),
            },
            {
              title: "Cap nhat lan cuoi",
              dataIndex: "lastSyncedAt",
              render: (value: string | null) => (value ? new Date(value).toLocaleString() : "-"),
            },
            {
              title: "Chi tiet",
              render: (_, record) => (
                <Space>
                  <Link to={`/stock-finance-charts/${record.ticker}`} aria-label={`Xem chi tiet ${record.ticker}`}>
                    <EyeOutlined />
                  </Link>
                  <Link
                    to={`/stock-finance-charts/${record.ticker}?editAssessment=1`}
                    aria-label={`Viet danh gia ${record.ticker}`}
                  >
                    <EditOutlined />
                  </Link>
                </Space>
              ),
            },
          ]}
          pagination={{
            current: data.page + 1,
            pageSize: data.size,
            total: data.totalElements,
            showSizeChanger: true,
            onChange: (page, pageSize) => {
              void loadTickers(page - 1, pageSize, tickerFilter);
            },
          }}
          scroll={{ x: 980 }}
        />
      </Card>
    </Space>
  );
}
