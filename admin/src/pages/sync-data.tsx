import { Button, Card, Popconfirm, Progress, Space, Spin, Typography } from "antd";
import { useEffect, useRef, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type SyncStatus = {
  running: boolean;
  received: number;
  totalUnique: number;
  processed: number;
  synced: number;
  phase: string;
  error: string | null;
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
  startedAt: string | null;
  finishedAt: string | null;
  lastError: string | null;
};

export function SyncDataPage() {
  const [syncing, setSyncing] = useState(false);
  const [historySyncing, setHistorySyncing] = useState(false);
  const [chartSyncStatus, setChartSyncStatus] = useState<StockFinanceChartSyncStatus | null>(null);
  const stockPollRef = useRef<number | null>(null);
  const historyPollRef = useRef<number | null>(null);

  const [stockStatus, setStockStatus] = useState<SyncStatus>({
    running: false,
    received: 0,
    totalUnique: 0,
    processed: 0,
    synced: 0,
    phase: "Idle",
    error: null,
  });

  const [historyStatus, setHistoryStatus] = useState<HistorySyncStatus>({
    running: false,
    mode: "INCREMENTAL",
    days: 7,
    totalSymbols: 0,
    processedSymbols: 0,
    failedSymbols: 0,
    recordsUpdated: 0,
    phase: "Idle",
    error: null,
  });

  async function fetchStockStatus() {
    const res = await apiClient.get<ApiEnvelope<SyncStatus>>("/admin/stocks/sync/status");
    setStockStatus(res.data.data);
    setSyncing(res.data.data.running);
    return res.data.data;
  }

  async function fetchHistoryStatus() {
    const res = await apiClient.get<ApiEnvelope<HistorySyncStatus>>("/admin/stocks/history/sync/status");
    setHistoryStatus(res.data.data);
    setHistorySyncing(res.data.data.running);
    return res.data.data;
  }

  async function fetchChartSyncStatus() {
    const res = await apiClient.get<ApiEnvelope<StockFinanceChartSyncStatus>>("/admin/stock-finance-charts/sync/status");
    setChartSyncStatus(res.data.data);
    return res.data.data;
  }

  function startStockPolling() {
    if (stockPollRef.current !== null) {
      return;
    }
    stockPollRef.current = window.setInterval(() => {
      void fetchStockStatus().then((current) => {
        if (!current.running) {
          stopStockPolling();
        }
      });
    }, 800);
  }

  function stopStockPolling() {
    if (stockPollRef.current !== null) {
      window.clearInterval(stockPollRef.current);
      stockPollRef.current = null;
    }
  }

  function startHistoryPolling() {
    if (historyPollRef.current !== null) {
      return;
    }
    historyPollRef.current = window.setInterval(() => {
      void fetchHistoryStatus().then((current) => {
        if (!current.running) {
          stopHistoryPolling();
        }
      });
    }, 1000);
  }

  function stopHistoryPolling() {
    if (historyPollRef.current !== null) {
      window.clearInterval(historyPollRef.current);
      historyPollRef.current = null;
    }
  }

  async function syncStocks() {
    if (syncing) {
      return;
    }
    setSyncing(true);
    try {
      await apiClient.post<ApiEnvelope<{ received: number; synced: number }>>("/admin/stocks/sync");
      await fetchStockStatus();
      startStockPolling();
    } catch {
      setSyncing(false);
    }
  }

  async function syncHistory() {
    if (historySyncing) {
      return;
    }
    setHistorySyncing(true);
    try {
      await apiClient.post<ApiEnvelope<HistorySyncStatus>>("/admin/stocks/history/sync");
      await fetchHistoryStatus();
      startHistoryPolling();
    } catch {
      setHistorySyncing(false);
    }
  }

  async function resetHistory() {
    if (historySyncing) {
      return;
    }
    setHistorySyncing(true);
    try {
      await apiClient.post<ApiEnvelope<HistorySyncStatus>>("/admin/stocks/history/sync/reset");
      await fetchHistoryStatus();
      startHistoryPolling();
    } catch {
      setHistorySyncing(false);
    }
  }

  useEffect(() => {
    void fetchStockStatus().then((current) => {
      if (current.running) {
        startStockPolling();
      }
    });
    void fetchHistoryStatus().then((current) => {
      if (current.running) {
        startHistoryPolling();
      }
    });
    void fetchChartSyncStatus();

    return () => {
      stopStockPolling();
      stopHistoryPolling();
    };
  }, []);

  const stockPercent =
    stockStatus.totalUnique > 0
      ? Math.min(100, Math.round((stockStatus.processed / stockStatus.totalUnique) * 100))
      : 0;

  const historyPercent =
    historyStatus.totalSymbols > 0
      ? Math.min(
          100,
          Math.round(
            ((historyStatus.processedSymbols + historyStatus.failedSymbols) / historyStatus.totalSymbols) * 100,
          ),
        )
      : 0;
  const chartSyncRunning = chartSyncStatus?.status === "RUNNING" || chartSyncStatus?.status === "PENDING";

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3}>Sync du lieu</Typography.Title>

      <Card title="Sync danh sach ma chung khoan">
        <Space>
          <Button type="primary" onClick={() => void syncStocks()} disabled={syncing}>
            Sync ma chung khoan
          </Button>
          {syncing ? (
            <Space>
              <Spin size="small" />
              <Typography.Text>
                Dang sync... {stockStatus.processed}/{stockStatus.totalUnique || "?"}
              </Typography.Text>
            </Space>
          ) : null}
        </Space>
        <div style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">
            Trang thai: {stockStatus.phase}
            {stockStatus.error ? ` - Loi: ${stockStatus.error}` : ""}
          </Typography.Text>
          <Progress percent={stockPercent} status={syncing ? "active" : "normal"} />
        </div>
      </Card>

      <Card title="Sync du lieu lich su">
        <Typography.Paragraph type="secondary" style={{ marginBottom: 12 }}>
          Reset se xoa sach bang <code>stock_histories</code> va tai lai khoang 200 phien gan nhat cho tat ca ma.
          Sync thuong chi bo sung du lieu moi va cap nhat lai vai ngay gan day, khong xoa lich su cu.
        </Typography.Paragraph>
        <Space>
          <Popconfirm
            title="Reset du lieu lich su?"
            description="Thao tac nay se xoa toan bo stock_histories va bootstrap lai tu dau."
            okText="Reset"
            cancelText="Huy"
            onConfirm={() => void resetHistory()}
            disabled={historySyncing || chartSyncRunning}
          >
            <Button
              danger
              loading={historySyncing && historyStatus.mode === "RESET"}
              disabled={syncing || historySyncing || chartSyncRunning}
            >
              Reset du lieu lich su
            </Button>
          </Popconfirm>
          <Button
            type="primary"
            onClick={() => void syncHistory()}
            loading={historySyncing && historyStatus.mode === "INCREMENTAL"}
            disabled={syncing || historySyncing || chartSyncRunning}
          >
            Sync du lieu lich su
          </Button>
          {historySyncing ? (
            <Space>
              <Spin size="small" />
              <Typography.Text>
                Dang sync... {historyStatus.processedSymbols}/{historyStatus.totalSymbols || "?"}
              </Typography.Text>
            </Space>
          ) : null}
        </Space>
        <div style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">
            Che do: {historyStatus.mode === "RESET" ? "RESET" : "INCREMENTAL"} |{" "}
            Trang thai: {historyStatus.phase}
            {historyStatus.error ? ` - Loi: ${historyStatus.error}` : ""}
          </Typography.Text>
          {chartSyncRunning ? (
            <Typography.Paragraph type="warning" style={{ marginTop: 8, marginBottom: 0 }}>
              Vietstock finance chart sync dang chay, tam khoa history sync de tranh lech du lieu.
            </Typography.Paragraph>
          ) : null}
          <Progress percent={historyPercent} status={historySyncing ? "active" : "normal"} />
        </div>
      </Card>
    </Space>
  );
}
