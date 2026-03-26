import { Alert, Button, Card, DatePicker, Descriptions, Drawer, Empty, Input, Space, Spin, Statistic, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type T0Status = {
  running: boolean;
  connected: boolean;
  phase: string;
  subscribedCount: number;
  subscribedTickers: number;
  lastMessageAt: string | null;
  lastSnapshotAt: string | null;
  lastSnapshotSlot: string | null;
  lastSnapshotCount: number;
  lastError: string | null;
  ssiForeignPhase?: string | null;
  lastForeignSyncAt?: string | null;
  nextForeignSyncAt?: string | null;
  foreignRefreshMinutes?: number;
  foreignStartTime?: string | null;
  foreignEndTime?: string | null;
  dnseKeyMasked: string | null;
  connectionStartedAt: string | null;
  authSuccessAt: string | null;
  lastReconnectAt: string | null;
  reconnectCount: number;
  updatedAt: string | null;
};

type T0SnapshotRow = {
  id: number;
  ticker: string;
  tradingDate: string;
  snapshotSlot: string;
  snapshotAt: string | null;
  totalMatchVol: number;
  totalMatchVal: number | string | null;
  foreignBuyVolTotal?: number;
  foreignSellVolTotal?: number;
  foreignBuyValTotal?: number | string | null;
  foreignSellValTotal?: number | string | null;
  netForeignVol?: number;
  netForeignVal?: number | string | null;
  foreignDataSource?: string | null;
  hasRawPayload: boolean;
  rawPayload: string | null;
  updatedAt: string | null;
  projection?: T0Projection;
};

type T0Projection = {
  projectionSlot: string | null;
  projectionLowerSlot?: string | null;
  projectionUpperSlot?: string | null;
  projectionSourceSlot?: string | null;
  projectionCurrentValue: number | string | null;
  projectionRatioAvg20: number | string | null;
  projectionRatioAvg5: number | string | null;
  projectionWeightedRatio: number | string | null;
  projectedTotalMatchVal: number | string | null;
  historicalWeightedRatio?: number | string | null;
  historicalProjectedTotalMatchVal?: number | string | null;
  historicalErrorPct?: number | string | null;
  timeWeightedRatio?: number | string | null;
  timeWeightedProjectedTotalMatchVal?: number | string | null;
  timeWeightedErrorPct?: number | string | null;
  projectionSample20: number;
  projectionSample5: number;
  projectionFinalSlot?: string | null;
  projectionWindow20?: number | null;
  projectionWindow5?: number | null;
  projectionWeight20?: number | string | null;
  projectionWeight5?: number | string | null;
  projectionInterpolationWeight?: number | string | null;
  projectionMethod?: string | null;
  projectionErrorPct?: number | string | null;
} | null;

type T0TimelineResponse = {
  ticker: string;
  tradingDate: string;
  timeline: T0SnapshotRow[];
  projection: T0Projection;
};

type CompactSnapshotRow = {
  key: string;
  ticker: string;
  tradingDate: string;
  hasRawPayload: boolean;
  snapshotCount: number;
  latestSlot: string | null;
  latestSnapshotAt: string | null;
  latestTotalMatchVol: number;
  latestTotalMatchVal: number | string | null;
  latestForeignNetVol?: number;
  latestForeignNetVal?: number | string | null;
  projection: T0Projection;
};

type PageResult<T> = {
  items: T[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

type T0DataMode = "snapshot" | "realtime";

function formatNumber(value: number | string | null | undefined) {
  const num = typeof value === "string" ? Number(value) : value ?? 0;
  if (!Number.isFinite(num)) {
    return "-";
  }
  return Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(num);
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return dayjs(value).format("DD/MM/YYYY HH:mm:ss");
}

function computeNextForeignSync(status: T0Status | null) {
  if (!status?.foreignRefreshMinutes || !status.foreignStartTime || !status.foreignEndTime) {
    return status?.nextForeignSyncAt ?? null;
  }
  if (status.nextForeignSyncAt) {
    return status.nextForeignSyncAt;
  }
  const now = dayjs();
  const start = dayjs(`${now.format("YYYY-MM-DD")} ${status.foreignStartTime}:00`);
  const end = dayjs(`${now.format("YYYY-MM-DD")} ${status.foreignEndTime}:00`);
  if (now.isBefore(start)) {
    return start.toISOString();
  }
  if (now.isAfter(end)) {
    return start.add(1, "day").toISOString();
  }
  if (status.lastForeignSyncAt) {
    const candidate = dayjs(status.lastForeignSyncAt).add(status.foreignRefreshMinutes, "minute");
    if (candidate.isBefore(end) || candidate.isSame(end)) {
      return candidate.toISOString();
    }
    return start.add(1, "day").toISOString();
  }
  return now.toISOString();
}

function formatPercent(value: number | string | null | undefined) {
  const num = typeof value === "string" ? Number(value) : value;
  if (num == null || !Number.isFinite(num)) {
    return "-";
  }
  return `${(num * 100).toFixed(1)}%`;
}

function renderErrorTag(value: number | string | null | undefined) {
  const num = typeof value === "string" ? Number(value) : value;
  if (num == null || !Number.isFinite(num)) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  const color = Math.abs(num) <= 5 ? "green" : Math.abs(num) <= 10 ? "gold" : "red";
  const prefix = num > 0 ? "+" : "";
  return <Tag color={color}>{`${prefix}${num.toFixed(2)}%`}</Tag>;
}

function renderProjectionLabel(projection: T0Projection) {
  if (!projection?.projectionSlot) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  return <Tag color="purple">{projection.projectionSlot}</Tag>;
}

function renderInterpolationSummary(projection: T0Projection) {
  if (!projection?.projectionLowerSlot || !projection?.projectionUpperSlot) {
    return "-";
  }
  if (projection.projectionLowerSlot === projection.projectionUpperSlot) {
    return `Trung moc ${projection.projectionLowerSlot}`;
  }
  const weight = typeof projection.projectionInterpolationWeight === "string"
    ? Number(projection.projectionInterpolationWeight)
    : projection.projectionInterpolationWeight;
  if (weight == null || !Number.isFinite(weight)) {
    return `${projection.projectionLowerSlot} -> ${projection.projectionUpperSlot}`;
  }
  return `${(weight * 100).toFixed(0)}% quang ${projection.projectionLowerSlot} -> ${projection.projectionUpperSlot}`;
}

function renderProjectionMethod(projection: T0Projection) {
  if (projection?.projectionMethod === "time_weighted_fallback") {
    return <Tag color="orange">Fallback theo thoi gian giao dich</Tag>;
  }
  if (projection?.projectionMethod === "historical_blend") {
    return <Tag color="green">Noi suy tu lich su</Tag>;
  }
  return <Typography.Text type="secondary">-</Typography.Text>;
}

function resolveEmptyDescription(status: T0Status | null) {
  if (!status) {
    return "Chua co snapshot T0.";
  }
  if (!status.running && status.phase === "Disabled") {
    return "Chua co snapshot T0 vi lich T0 dang tat. Vao Settings > T0 Snapshot Schedule de bat lich.";
  }
  if (!status.running && (status.phase === "Idle" || status.phase === "Stopped")) {
    return "Chua co snapshot T0 vi worker chua chay. Hay chay npm run dev:t0-worker.";
  }
  if (!status.connected && status.phase === "Missing DNSE credentials") {
    return "Chua co snapshot T0 vi thieu DNSE API key/secret trong Settings.";
  }
  if (!status.connected && status.phase === "No valid tickers") {
    return "Chua co snapshot T0 vi khong co ma 3 ky tu hop le trong danh sach stocks.";
  }
  if (status.connected || status.running) {
    return "Worker dang chay, nhung chua den moc snapshot hoac chua nhan du lieu realtime cho ngay da chon.";
  }
  return "Chua co snapshot T0 cho bo loc hien tai.";
}

export function T0DataPage() {
  const [loading, setLoading] = useState(false);
  const [statusLoading, setStatusLoading] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [rows, setRows] = useState<CompactSnapshotRow[]>([]);
  const [status, setStatus] = useState<T0Status | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tickerFilter, setTickerFilter] = useState("");
  const [dateFilter, setDateFilter] = useState(dayjs());
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [timeline, setTimeline] = useState<T0TimelineResponse | null>(null);
  const [selectedTimelineRowId, setSelectedTimelineRowId] = useState<number | null>(null);
  const [dataMode, setDataMode] = useState<T0DataMode>("snapshot");
  const lastSnapshotAtRef = useRef<string | null>(null);
  const emptyDescription = useMemo(() => resolveEmptyDescription(status), [status]);
  const nextForeignSyncAt = useMemo(() => computeNextForeignSync(status), [status]);
  const selectedTimelineRow = useMemo(
    () => timeline?.timeline.find((item) => item.id === selectedTimelineRowId) ?? timeline?.timeline.at(-1) ?? null,
    [selectedTimelineRowId, timeline],
  );

  async function loadStatus(options?: { silent?: boolean }) {
    if (!options?.silent) {
      setStatusLoading(true);
    }
    try {
      const res = await apiClient.get<ApiEnvelope<T0Status>>("/admin/stocks/t0-status");
      const nextStatus = res.data.data;
      const previousSnapshotAt = lastSnapshotAtRef.current;
      lastSnapshotAtRef.current = nextStatus.lastSnapshotAt;
      setStatus(nextStatus);
      if (
        options?.silent &&
        nextStatus.lastSnapshotAt &&
        nextStatus.lastSnapshotAt !== previousSnapshotAt
      ) {
        void loadSnapshots(pagination.current, pagination.pageSize, undefined, { silent: true });
      }
    } finally {
      if (!options?.silent) {
        setStatusLoading(false);
      }
    }
  }

  async function loadSnapshots(
    page = 1,
    pageSize = pagination.pageSize,
    nextFilters?: { ticker?: string; tradingDate?: string },
    options?: { silent?: boolean },
  ) {
    if (!options?.silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const fallbackTicker = tickerFilter.trim().toUpperCase();
      const resolvedTicker = nextFilters?.ticker !== undefined ? nextFilters.ticker : (fallbackTicker || undefined);
      const resolvedTradingDate = nextFilters?.tradingDate ?? dateFilter.format("YYYY-MM-DD");
      const snapshotRes = await apiClient.get<ApiEnvelope<PageResult<Omit<CompactSnapshotRow, "key">>>>("/admin/stocks/t0-snapshots", {
        params: {
          page: page - 1,
          size: pageSize,
          ticker: resolvedTicker,
          tradingDate: resolvedTradingDate,
        },
      });
      let result = snapshotRes.data.data;
      let nextMode: T0DataMode = "snapshot";
      if (!result.items.length) {
        const realtimeRes = await apiClient.get<ApiEnvelope<PageResult<Omit<CompactSnapshotRow, "key">>>>("/admin/stocks/t0-realtime", {
          params: {
            page: page - 1,
            size: pageSize,
            ticker: resolvedTicker,
            tradingDate: resolvedTradingDate,
          },
        });
        if (realtimeRes.data.data.items.length) {
          result = realtimeRes.data.data;
          nextMode = "realtime";
        }
      }
      setDataMode(nextMode);
      setRows(
        result.items.map((item) => ({
          ...item,
          key: `${item.ticker}-${item.tradingDate}`,
        })),
      );
      setPagination({
        current: result.page + 1,
        pageSize: result.size,
        total: result.totalElements,
      });
    } catch (caught) {
      console.error(caught);
      setRows([]);
      setDataMode("snapshot");
      if (!options?.silent) {
        setError("Khong tai duoc danh sach snapshot T0.");
      }
    } finally {
      if (!options?.silent) {
        setLoading(false);
      }
    }
  }

  async function openTimeline(row: T0SnapshotRow) {
    setTimelineOpen(true);
    setTimelineLoading(true);
    try {
      const res = await apiClient.get<ApiEnvelope<T0TimelineResponse>>(`/admin/stocks/t0-snapshots/${row.ticker}`, {
        params: { tradingDate: row.tradingDate },
      });
      setTimeline(res.data.data);
      setSelectedTimelineRowId(res.data.data.timeline.at(-1)?.id ?? null);
    } finally {
      setTimelineLoading(false);
    }
  }

  useEffect(() => {
    void Promise.all([loadStatus(), loadSnapshots(1, pagination.pageSize)]);
    const timer = window.setInterval(() => {
      void loadStatus({ silent: true });
    }, 15000);
    return () => window.clearInterval(timer);
  }, []);

  const columns: ColumnsType<CompactSnapshotRow> = useMemo(
    () => [
      {
        title: "Ticker",
        dataIndex: "ticker",
        width: 100,
        render: (value: string) => <Typography.Text strong>{value}</Typography.Text>,
      },
      {
        title: "Ngay",
        dataIndex: "tradingDate",
        width: 120,
      },
      {
        title: "Slot tinh",
        width: 110,
        render: (_: unknown, row: CompactSnapshotRow) => renderProjectionLabel(row.projection),
      },
      {
        title: "GTDK",
        align: "right",
        width: 140,
        render: (_: unknown, row: CompactSnapshotRow) => formatNumber(row.projection?.projectedTotalMatchVal),
      },
      {
        title: "So moc",
        width: 90,
        render: (_: unknown, row: CompactSnapshotRow) => <Tag color="blue">{row.snapshotCount}</Tag>,
      },
      {
        title: "Moc cuoi",
        width: 110,
        render: (_: unknown, row: CompactSnapshotRow) =>
          row.latestSlot ? <Tag color="gold">{row.latestSlot}</Tag> : <Typography.Text type="secondary">-</Typography.Text>,
      },
      {
        title: "Cap nhat",
        width: 180,
        render: (_: unknown, row: CompactSnapshotRow) => formatDateTime(row.latestSnapshotAt),
      },
      {
        title: "Vol cuoi",
        align: "right",
        width: 140,
        render: (_: unknown, row: CompactSnapshotRow) => formatNumber(row.latestTotalMatchVol),
      },
      {
        title: "Gia tri cuoi",
        align: "right",
        width: 140,
        render: (_: unknown, row: CompactSnapshotRow) => formatNumber(row.latestTotalMatchVal),
      },
      {
        title: "NN net vol",
        align: "right",
        width: 120,
        render: (_: unknown, row: CompactSnapshotRow) => formatNumber(row.latestForeignNetVol),
      },
      {
        title: "NN net val",
        align: "right",
        width: 130,
        render: (_: unknown, row: CompactSnapshotRow) => formatNumber(row.latestForeignNetVal),
      },
      {
        title: "Raw",
        width: 100,
        render: (_: unknown, row: CompactSnapshotRow) => (row.hasRawPayload ? <Tag color="green">Co</Tag> : <Tag>Khong</Tag>),
      },
    ],
    [],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large" className="t0-page">
      <div>
        <Typography.Title level={3} style={{ marginBottom: 0 }}>
          Du lieu T0
        </Typography.Title>
        <Typography.Text type="secondary">
          Theo doi snapshot luy ke trong ngay tu DNSE websocket, kem giao dich nuoc ngoai intraday duoc dong bo dinh ky tu SSI board.
        </Typography.Text>
      </div>

      <Card className="t0-status-card">
        <Space size="large" wrap className="t0-status-stats">
          <Statistic title="Worker" value={status?.connected ? "Connected" : status?.running ? "Running" : "Stopped"} />
          <Statistic title="Phase" value={status?.phase ?? "-"} />
          <Statistic title="Subscribed" value={status?.subscribedCount ?? 0} />
          <Statistic title="Last Snapshot" value={status?.lastSnapshotSlot ?? "-"} />
        </Space>
        {statusLoading ? <Typography.Text type="secondary">Dang tai trang thai...</Typography.Text> : null}
        <Descriptions size="small" column={2} style={{ marginTop: 16 }} className="t0-status-descriptions">
          <Descriptions.Item label="DNSE key">{status?.dnseKeyMasked ?? "-"}</Descriptions.Item>
          <Descriptions.Item label="Auth success">{formatDateTime(status?.authSuccessAt)}</Descriptions.Item>
          <Descriptions.Item label="Connection started">{formatDateTime(status?.connectionStartedAt)}</Descriptions.Item>
          <Descriptions.Item label="Last reconnect">{formatDateTime(status?.lastReconnectAt)}</Descriptions.Item>
          <Descriptions.Item label="Last message">{formatDateTime(status?.lastMessageAt)}</Descriptions.Item>
          <Descriptions.Item label="Foreign sync at">{formatDateTime(status?.lastForeignSyncAt)}</Descriptions.Item>
          <Descriptions.Item label="Foreign next sync">{formatDateTime(nextForeignSyncAt)}</Descriptions.Item>
          <Descriptions.Item label="Foreign chu ky">{status?.foreignRefreshMinutes ? `${status.foreignRefreshMinutes} phut` : "-"}</Descriptions.Item>
          <Descriptions.Item label="Foreign cua so">{status?.foreignStartTime && status?.foreignEndTime ? `${status.foreignStartTime} - ${status.foreignEndTime}` : "-"}</Descriptions.Item>
          <Descriptions.Item label="Last snapshot at">{formatDateTime(status?.lastSnapshotAt)}</Descriptions.Item>
          <Descriptions.Item label="Reconnect count">{status?.reconnectCount ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Snapshot count">{status?.lastSnapshotCount ?? 0}</Descriptions.Item>
          <Descriptions.Item label="Updated at">{formatDateTime(status?.updatedAt)}</Descriptions.Item>
          <Descriptions.Item label="Foreign T0">{status?.ssiForeignPhase ?? "-"}</Descriptions.Item>
        </Descriptions>
        {status?.lastError ? <Alert style={{ marginTop: 12 }} type="warning" showIcon message={status.lastError} /> : null}
      </Card>

      <Card>
        <Space wrap>
          <DatePicker value={dateFilter} onChange={(value) => setDateFilter(value ?? dayjs())} format="DD/MM/YYYY" />
          <Input
            value={tickerFilter}
            placeholder="Loc theo ma CK"
            onChange={(event) => setTickerFilter(event.target.value.toUpperCase())}
            style={{ width: 180 }}
            maxLength={10}
          />
          <Button
            type="primary"
            onClick={() => void loadSnapshots(1, pagination.pageSize)}
            loading={loading}
          >
            Loc du lieu
          </Button>
          <Button
            onClick={() => {
              setTickerFilter("");
              const today = dayjs();
              setDateFilter(today);
              void loadSnapshots(1, pagination.pageSize, { ticker: undefined, tradingDate: today.format("YYYY-MM-DD") });
            }}
          >
            Hom nay
          </Button>
          <Button
            onClick={() => void Promise.all([loadStatus(), loadSnapshots(pagination.current, pagination.pageSize)])}
          >
            Lam moi
          </Button>
        </Space>
      </Card>

      {error ? <Alert type="error" showIcon message={error} /> : null}

      <Card title={dataMode === "realtime" ? "Bang realtime T0" : "Bang snapshot T0"}>
        {dataMode === "realtime" ? (
          <Alert
            style={{ marginBottom: 16 }}
            type="info"
            showIcon
            message="Dang hien du lieu realtime do chua co snapshot cho ngay da chon."
          />
        ) : null}
        {loading && !rows.length ? (
          <div style={{ minHeight: 240, display: "grid", placeItems: "center" }}>
            <Spin />
          </div>
        ) : rows.length ? (
          <Table<CompactSnapshotRow>
            rowKey="key"
            dataSource={rows}
            columns={columns}
            loading={loading}
            onRow={(row) =>
              dataMode === "snapshot"
                ? {
                    onClick: () =>
                      void openTimeline({
                        id: 0,
                        ticker: row.ticker,
                        tradingDate: row.tradingDate,
                        snapshotSlot: "",
                        snapshotAt: null,
                        totalMatchVol: 0,
                        totalMatchVal: 0,
                        foreignBuyVolTotal: 0,
                        foreignSellVolTotal: 0,
                        foreignBuyValTotal: 0,
                        foreignSellValTotal: 0,
                        netForeignVol: 0,
                        netForeignVal: 0,
                        hasRawPayload: row.hasRawPayload,
                        rawPayload: null,
                        updatedAt: null,
                      }),
                    style: { cursor: "pointer" },
                  }
                : {}
            }
            scroll={{ x: 1100 }}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: pagination.total,
              onChange: (page, pageSize) => void loadSnapshots(page, pageSize),
            }}
          />
        ) : (
          <Empty description={emptyDescription} />
        )}
      </Card>

      <Drawer
        title={timeline ? `Du lieu trong ngay ${timeline.ticker}` : "Du lieu trong ngay"}
        width={720}
        open={timelineOpen}
        onClose={() => {
          setTimelineOpen(false);
          setSelectedTimelineRowId(null);
        }}
      >
        {timelineLoading ? (
          <div style={{ minHeight: 200, display: "grid", placeItems: "center" }}>
            <Spin />
          </div>
        ) : timeline?.timeline.length ? (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Descriptions size="small" column={2} className="t0-timeline-descriptions">
              <Descriptions.Item label="Ticker">{timeline.ticker}</Descriptions.Item>
              <Descriptions.Item label="Ngay">{timeline.tradingDate}</Descriptions.Item>
              <Descriptions.Item label="Row dang xem">{selectedTimelineRow?.snapshotSlot ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="Snapshot at">{formatDateTime(selectedTimelineRow?.snapshotAt)}</Descriptions.Item>
              <Descriptions.Item label="Slot tinh">{renderProjectionLabel(selectedTimelineRow?.projection ?? null)}</Descriptions.Item>
              <Descriptions.Item label="GTDK">{formatNumber(selectedTimelineRow?.projection?.projectedTotalMatchVal)}</Descriptions.Item>
              <Descriptions.Item label="GTDK theo lich su">{formatNumber(selectedTimelineRow?.projection?.historicalProjectedTotalMatchVal)}</Descriptions.Item>
              <Descriptions.Item label="Lech final theo lich su">{renderErrorTag(selectedTimelineRow?.projection?.historicalErrorPct)}</Descriptions.Item>
              <Descriptions.Item label="GTDK theo thoi gian">{formatNumber(selectedTimelineRow?.projection?.timeWeightedProjectedTotalMatchVal)}</Descriptions.Item>
              <Descriptions.Item label="Lech final theo thoi gian">{renderErrorTag(selectedTimelineRow?.projection?.timeWeightedErrorPct)}</Descriptions.Item>
              <Descriptions.Item label="Moc du lieu hien tai">{selectedTimelineRow?.projection?.projectionSourceSlot ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="Phuong phap tinh">{renderProjectionMethod(selectedTimelineRow?.projection ?? null)}</Descriptions.Item>
              <Descriptions.Item label="Cach noi suy">{renderInterpolationSummary(selectedTimelineRow?.projection ?? null)}</Descriptions.Item>
              <Descriptions.Item label="Moc chot cuoi ngay">{selectedTimelineRow?.projection?.projectionFinalSlot ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="Gia tri hien tai">{formatNumber(selectedTimelineRow?.projection?.projectionCurrentValue)}</Descriptions.Item>
              <Descriptions.Item label="Ti le TB dai">{formatPercent(selectedTimelineRow?.projection?.projectionRatioAvg20)}</Descriptions.Item>
              <Descriptions.Item label="Ti le TB ngan">{formatPercent(selectedTimelineRow?.projection?.projectionRatioAvg5)}</Descriptions.Item>
              <Descriptions.Item label="Ti le dung de tinh">{formatPercent(selectedTimelineRow?.projection?.projectionWeightedRatio)}</Descriptions.Item>
              <Descriptions.Item label="Ti le theo lich su">{formatPercent(selectedTimelineRow?.projection?.historicalWeightedRatio)}</Descriptions.Item>
              <Descriptions.Item label="Ti le theo thoi gian">{formatPercent(selectedTimelineRow?.projection?.timeWeightedRatio)}</Descriptions.Item>
              <Descriptions.Item label="So phien TB dai">{selectedTimelineRow?.projection?.projectionWindow20 ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="So phien TB ngan">{selectedTimelineRow?.projection?.projectionWindow5 ?? "-"}</Descriptions.Item>
              <Descriptions.Item label="Trong so TB dai">{formatPercent(selectedTimelineRow?.projection?.projectionWeight20)}</Descriptions.Item>
              <Descriptions.Item label="Trong so TB ngan">{formatPercent(selectedTimelineRow?.projection?.projectionWeight5)}</Descriptions.Item>
            </Descriptions>
            <Table<T0SnapshotRow>
              rowKey="id"
              dataSource={timeline.timeline}
              onRow={(row) => ({
                onClick: () => setSelectedTimelineRowId(row.id),
                style: { cursor: "pointer" },
              })}
              rowClassName={(row) => (row.id === selectedTimelineRowId ? "ant-table-row-selected" : "")}
              pagination={false}
              columns={[
                { title: "Slot", dataIndex: "snapshotSlot", width: 90, render: (value) => <Tag color="blue">{value}</Tag> },
                { title: "Snapshot At", dataIndex: "snapshotAt", width: 180, render: (value) => formatDateTime(value) },
                { title: "Vol luy ke", dataIndex: "totalMatchVol", align: "right", render: (value) => formatNumber(value) },
                { title: "Gia tri luy ke", dataIndex: "totalMatchVal", align: "right", render: (value) => formatNumber(value) },
                { title: "NN mua vol", dataIndex: "foreignBuyVolTotal", align: "right", render: (value) => formatNumber(value) },
                { title: "NN ban vol", dataIndex: "foreignSellVolTotal", align: "right", render: (value) => formatNumber(value) },
                { title: "NN net vol", dataIndex: "netForeignVol", align: "right", render: (value) => formatNumber(value) },
                { title: "NN net val", dataIndex: "netForeignVal", align: "right", render: (value) => formatNumber(value) },
                {
                  title: "GTDK active",
                  width: 130,
                  align: "right",
                  render: (_, row) => formatNumber(row.projection?.projectedTotalMatchVal),
                },
                {
                  title: "Lech active",
                  width: 120,
                  align: "right",
                  render: (_, row) => renderErrorTag(row.projection?.projectionErrorPct),
                },
                {
                  title: "GTDK theo lich su",
                  width: 150,
                  align: "right",
                  render: (_, row) => formatNumber(row.projection?.historicalProjectedTotalMatchVal),
                },
                {
                  title: "Lech final theo lich su",
                  width: 170,
                  align: "right",
                  render: (_, row) => renderErrorTag(row.projection?.historicalErrorPct),
                },
                {
                  title: "GTDK theo thoi gian",
                  width: 165,
                  align: "right",
                  render: (_, row) => formatNumber(row.projection?.timeWeightedProjectedTotalMatchVal),
                },
                {
                  title: "Lech final theo thoi gian",
                  width: 180,
                  align: "right",
                  render: (_, row) => renderErrorTag(row.projection?.timeWeightedErrorPct),
                },
                {
                  title: "Cach tinh",
                  width: 180,
                  render: (_, row) => renderProjectionMethod(row.projection ?? null),
                },
                {
                  title: "Raw",
                  width: 100,
                  render: (_, row) => (row.hasRawPayload ? <Tag color="green">Co</Tag> : <Tag>Khong</Tag>),
                },
              ]}
            />
          </Space>
        ) : (
          <Empty description="Khong co du lieu trong ngay" />
        )}
      </Drawer>
    </Space>
  );
}
