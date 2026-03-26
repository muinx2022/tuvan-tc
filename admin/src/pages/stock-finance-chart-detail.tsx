import { ArrowLeftOutlined, EditOutlined, ReloadOutlined, SaveOutlined } from "@ant-design/icons";
import { Button, Card, Descriptions, Empty, Space, Table, Tabs, Tag, Typography, message, theme } from "antd";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { RichTextEditor, type RichTextEditorHandle } from "../components/editor/RichTextEditor";
import { apiClient, type ApiEnvelope } from "../lib/api";

type StockFinanceChartSnapshot = {
  id: number;
  stockSymbolId: number;
  ticker: string;
  chartMenuId: number;
  chartName: string;
  reportType: string;
  reportPeriod: string | null;
  processingStatus: string;
  companyAssessment: string | null;
  dataJson: string;
  createdAt: string;
  updatedAt: string;
};

type StockFinanceChartDetailPage = {
  stockSymbolId: number;
  ticker: string;
  snapshotCount: number;
  syncedAt: string | null;
  overviewAssessment: string | null;
  items: StockFinanceChartSnapshot[];
};

type StockFinanceChartAssessmentResponse = {
  stockSymbolId: number;
  ticker: string;
  overviewAssessment: string | null;
  assessmentStatus: string;
  sourceSyncedAt: string | null;
  updatedAt: string | null;
};

type RawChartDetail = {
  ChartMenuID?: number;
  ReportNormID?: number;
  ReportNormName?: string;
  NormTerm?: string;
  Color?: string;
  ChartType?: string;
  Value?: number | null;
  Unit?: string | null;
  ValueSumPeriod?: number | null;
  PeriodNumber?: number | null;
};

type ParsedSeries = {
  key: string;
  name: string;
  color: string;
  chartType: string;
  unit: string | null;
  values: Array<number | null>;
};

type ParsedData = {
  chart: Record<string, unknown> | null;
  details: RawChartDetail[];
  terms: string[];
  series: ParsedSeries[];
};

type ParsedSnapshot = StockFinanceChartSnapshot & {
  parsed: ParsedData | null;
};

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function looksLikeHtml(value: string) {
  return /<[^>]+>/.test(value);
}

function assessmentToHtml(value: string | null | undefined) {
  const raw = (value ?? "").trim();
  if (!raw) {
    return "";
  }
  if (looksLikeHtml(raw)) {
    return raw;
  }
  return raw
    .split(/\r?\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${escapeHtml(line)}</p>`)
    .join("");
}

function formatNumber(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) {
    return "-";
  }
  return new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value);
}

function parseSnapshot(snapshot: StockFinanceChartSnapshot): ParsedSnapshot {
  try {
    const parsed = JSON.parse(snapshot.dataJson) as { chart?: Record<string, unknown>; details?: RawChartDetail[] };
    const details = Array.isArray(parsed.details) ? parsed.details : [];
    const termSet = new Set<string>();
    for (const item of details) {
      if (item.NormTerm) {
        termSet.add(item.NormTerm);
      }
    }
    const terms = Array.from(termSet);
    const seriesMap = new Map<string, ParsedSeries>();
    for (const item of details) {
      const name = item.ReportNormName?.trim() || `Series ${item.ReportNormID ?? ""}`.trim();
      const key = `${item.ReportNormID ?? name}-${name}`;
      if (!seriesMap.has(key)) {
        seriesMap.set(key, {
          key,
          name,
          color: item.Color || "#4e79a7",
          chartType: item.ChartType || "spline",
          unit: item.Unit || null,
          values: Array.from({ length: terms.length }, () => null),
        });
      }
      const series = seriesMap.get(key)!;
      const index = terms.findIndex((term) => term === item.NormTerm);
      if (index >= 0) {
        series.values[index] = item.Value ?? null;
      }
    }
    return {
      ...snapshot,
      parsed: {
        chart: parsed.chart ?? null,
        details,
        terms,
        series: Array.from(seriesMap.values()),
      },
    };
  } catch {
    return { ...snapshot, parsed: null };
  }
}

function buildChartRange(series: ParsedSeries[]) {
  const values = series.flatMap((item) => item.values).filter((value): value is number => value != null);
  if (!values.length) {
    return { min: 0, max: 100 };
  }
  let min = Math.min(...values, 0);
  let max = Math.max(...values, 0);
  if (min === max) {
    max += 1;
    min -= 1;
  }
  const padding = (max - min) * 0.15;
  return { min: min - padding, max: max + padding };
}

function FinanceChartPreview({ snapshot }: { snapshot: ParsedSnapshot }) {
  const { token } = theme.useToken();

  if (!snapshot.parsed || !snapshot.parsed.series.length || !snapshot.parsed.terms.length) {
    return <Empty description="Khong co du lieu chart de ve" />;
  }

  const width = 940;
  const height = 340;
  const padding = { top: 22, right: 26, bottom: 54, left: 48 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const { terms, series } = snapshot.parsed;
  const range = buildChartRange(series);
  const maxTermCount = Math.max(terms.length, 1);
  const stepX = innerWidth / maxTermCount;
  const allStacked = series.every((item) => item.chartType.includes("stacked"));
  const hasColumns = series.some((item) => item.chartType.includes("column"));
  const hasLines = series.some((item) => item.chartType.includes("spline"));

  const yForValue = (value: number) => {
    const ratio = (value - range.min) / (range.max - range.min);
    return padding.top + innerHeight - ratio * innerHeight;
  };

  const zeroY = yForValue(0);
  const barGroups = terms.map((_, termIndex) => {
    if (!hasColumns) {
      return [];
    }
    const columnSeries = series.filter((item) => item.chartType.includes("column"));
    if (allStacked) {
      let positiveBase = 0;
      let negativeBase = 0;
      return columnSeries.map((item) => {
        const value = item.values[termIndex] ?? 0;
        const from = value >= 0 ? positiveBase : negativeBase;
        const to = from + value;
        if (value >= 0) {
          positiveBase = to;
        } else {
          negativeBase = to;
        }
        const y1 = yForValue(Math.max(from, to));
        const y2 = yForValue(Math.min(from, to));
        return {
          key: `${item.key}-${termIndex}`,
          x: padding.left + termIndex * stepX + stepX * 0.18,
          width: stepX * 0.64,
          y: y1,
          height: Math.max(1, y2 - y1),
          color: item.color,
        };
      });
    }
    const barWidth = Math.max(8, (stepX * 0.72) / Math.max(columnSeries.length, 1));
    return columnSeries.map((item, seriesIndex) => {
      const value = item.values[termIndex] ?? 0;
      const x = padding.left + termIndex * stepX + stepX * 0.14 + seriesIndex * barWidth;
      const y = value >= 0 ? yForValue(value) : zeroY;
      const heightPx = Math.max(1, Math.abs(yForValue(value) - zeroY));
      return {
        key: `${item.key}-${termIndex}`,
        x,
        width: Math.max(6, barWidth - 4),
        y,
        height: heightPx,
        color: item.color,
      };
    });
  });

  const lineSeries = series.filter((item) => item.chartType.includes("spline"));

  return (
    <div
      style={{
        borderRadius: 16,
        border: `1px solid ${token.colorBorderSecondary}`,
        background: token.colorBgContainer,
        overflow: "hidden",
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "14px 16px 0" }}>
        {series.map((item) => (
          <Space key={item.key} size={8}>
            <span
              style={{
                width: 11,
                height: 11,
                borderRadius: item.chartType.includes("spline") ? 999 : 2,
                background: item.color,
                display: "inline-block",
              }}
            />
            <Typography.Text style={{ color: token.colorTextSecondary }}>{item.name}</Typography.Text>
          </Space>
        ))}
      </div>
      <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: 380, display: "block" }}>
        <rect x="0" y="0" width={width} height={height} fill={token.colorBgContainer} />
        {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
          const value = range.max - tick * (range.max - range.min);
          const y = yForValue(value);
          return (
            <g key={tick}>
              <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} stroke={token.colorBorderSecondary} />
              <text x={8} y={y + 4} fill={token.colorTextTertiary} fontSize={11}>
                {formatNumber(value)}
              </text>
            </g>
          );
        })}
        <line x1={padding.left} y1={zeroY} x2={width - padding.right} y2={zeroY} stroke={token.colorTextQuaternary} />
        {barGroups.flat().map((bar) => (
          <rect key={bar.key} x={bar.x} y={bar.y} width={bar.width} height={bar.height} rx={allStacked ? 0 : 3} fill={bar.color} opacity={0.92} />
        ))}
        {lineSeries.map((item) => {
          const path = item.values
            .map((value, index) => {
              if (value == null) {
                return null;
              }
              const x = padding.left + index * stepX + stepX / 2;
              const y = yForValue(value);
              return `${index === 0 ? "M" : "L"} ${x} ${y}`;
            })
            .filter(Boolean)
            .join(" ");
          return (
            <g key={item.key}>
              <path d={path} fill="none" stroke={item.color} strokeWidth={3} strokeLinejoin="round" strokeLinecap="round" />
              {item.values.map((value, index) =>
                value == null ? null : (
                  <circle key={`${item.key}-${index}`} cx={padding.left + index * stepX + stepX / 2} cy={yForValue(value)} r={3.5} fill={item.color} />
                ),
              )}
            </g>
          );
        })}
        {terms.map((term, index) => {
          const x = padding.left + index * stepX + stepX / 2;
          return (
            <g key={term}>
              <text
                x={x}
                y={height - 14}
                textAnchor="end"
                transform={`rotate(-45 ${x} ${height - 14})`}
                fill={token.colorTextTertiary}
                fontSize={11}
              >
                {term}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ padding: "0 16px 16px" }}>
        <Space wrap>
          <Tag color={snapshot.reportType === "YEAR" ? "gold" : "blue"}>{snapshot.reportType}</Tag>
          {hasLines ? <Tag>Line</Tag> : null}
          {hasColumns ? <Tag>Column</Tag> : null}
          {allStacked ? <Tag color="purple">Stacked</Tag> : null}
          {snapshot.reportPeriod ? <Tag>{snapshot.reportPeriod}</Tag> : null}
        </Space>
      </div>
    </div>
  );
}

function SnapshotTable({ snapshot }: { snapshot: ParsedSnapshot }) {
  const rows = snapshot.parsed?.details ?? [];
  return (
    <Table<RawChartDetail>
      rowKey={(record, index) => `${record.ReportNormID}-${record.NormTerm}-${index}`}
      size="small"
      pagination={{ pageSize: 12, showSizeChanger: false }}
      scroll={{ x: 1000 }}
      dataSource={rows}
      columns={[
        { title: "Norm term", dataIndex: "NormTerm", width: 110 },
        { title: "Chi so", dataIndex: "ReportNormName", width: 280 },
        { title: "Chart type", dataIndex: "ChartType", width: 140 },
        { title: "Value", dataIndex: "Value", width: 140, align: "right", render: (value: number | null | undefined) => formatNumber(value) },
        { title: "Value sum", dataIndex: "ValueSumPeriod", width: 140, align: "right", render: (value: number | null | undefined) => formatNumber(value) },
        { title: "Unit", dataIndex: "Unit", width: 100 },
        { title: "Norm ID", dataIndex: "ReportNormID", width: 100 },
      ]}
    />
  );
}

function SnapshotCard({ snapshot }: { snapshot: ParsedSnapshot }) {
  return (
    <Card
      title={
        <Space wrap>
          <Typography.Text strong>{snapshot.chartName}</Typography.Text>
          <Tag color={snapshot.reportType === "YEAR" ? "gold" : "blue"}>{snapshot.reportType}</Tag>
          <Tag>ChartMenuID: {snapshot.chartMenuId}</Tag>
          <Tag color={snapshot.processingStatus === "RAW" ? "default" : "green"}>{snapshot.processingStatus}</Tag>
        </Space>
      }
    >
      <Space direction="vertical" style={{ width: "100%" }} size="middle">
        <Descriptions size="small" column={4} bordered>
          <Descriptions.Item label="Thoi diem bao cao">{snapshot.reportPeriod || "-"}</Descriptions.Item>
          <Descriptions.Item label="Cap nhat">{new Date(snapshot.updatedAt).toLocaleString()}</Descriptions.Item>
        </Descriptions>

        <Tabs
          defaultActiveKey="chart"
          items={[
            { key: "chart", label: "Chart", children: <FinanceChartPreview snapshot={snapshot} /> },
            { key: "table", label: "Table", children: <SnapshotTable snapshot={snapshot} /> },
            {
              key: "json",
              label: "JSON",
              children: (
                <Typography.Paragraph copyable style={{ whiteSpace: "pre-wrap", marginBottom: 0, maxHeight: 420, overflow: "auto" }}>
                  {snapshot.dataJson}
                </Typography.Paragraph>
              ),
            },
          ]}
        />
      </Space>
    </Card>
  );
}

export function StockFinanceChartDetailPage() {
  const params = useParams<{ ticker: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const ticker = params.ticker?.toUpperCase() ?? "";
  const [loading, setLoading] = useState(false);
  const [savingAssessment, setSavingAssessment] = useState(false);
  const [editingAssessment, setEditingAssessment] = useState(searchParams.get("editAssessment") === "1");
  const [assessmentDraft, setAssessmentDraft] = useState("");
  const [editorResetToken, setEditorResetToken] = useState(0);
  const [data, setData] = useState<StockFinanceChartDetailPage | null>(null);
  const editorRef = useRef<RichTextEditorHandle | null>(null);

  async function load() {
    if (!ticker) {
      return;
    }
    setLoading(true);
    try {
      const res = await apiClient.get<ApiEnvelope<StockFinanceChartDetailPage>>(`/admin/stock-finance-charts/${ticker}`);
      setData(res.data.data);
      setAssessmentDraft(assessmentToHtml(res.data.data.overviewAssessment));
      setEditorResetToken((prev) => prev + 1);
    } finally {
      setLoading(false);
    }
  }

  async function saveAssessment() {
    if (!ticker) {
      return;
    }
    setSavingAssessment(true);
    try {
      const resolvedAssessment = await editorRef.current?.resolveContentBeforeSubmit() ?? assessmentDraft;
      const res = await apiClient.put<ApiEnvelope<StockFinanceChartAssessmentResponse>>(
        `/admin/stock-finance-charts/${ticker}/assessment`,
        {
          overviewAssessment: resolvedAssessment,
        },
      );
      setData((current) =>
        current
          ? {
              ...current,
              overviewAssessment: res.data.data.overviewAssessment,
            }
          : current,
      );
      setAssessmentDraft(assessmentToHtml(res.data.data.overviewAssessment));
      setEditorResetToken((prev) => prev + 1);
      setEditingAssessment(false);
      if (searchParams.get("editAssessment") === "1") {
        searchParams.delete("editAssessment");
        setSearchParams(searchParams, { replace: true });
      }
      message.success("Luu danh gia thanh cong");
    } finally {
      setSavingAssessment(false);
    }
  }

  useEffect(() => {
    void load();
  }, [ticker]);

  useEffect(() => {
    const shouldEdit = searchParams.get("editAssessment") === "1";
    setEditingAssessment(shouldEdit);
  }, [searchParams]);

  const snapshots = useMemo(() => (data?.items ?? []).map(parseSnapshot), [data?.items]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Space>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          Danh sach ma da quet
        </Button>
      </Space>
      <Typography.Title level={3}>Vietstock Finance Charts - {ticker || "-"}</Typography.Title>
      <Card loading={loading}>
        <Space wrap style={{ width: "100%", justifyContent: "space-between" }}>
          <Descriptions size="small" column={4}>
            <Descriptions.Item label="Ticker">{data?.ticker ?? ticker}</Descriptions.Item>
            <Descriptions.Item label="Stock ID">{data?.stockSymbolId ?? "-"}</Descriptions.Item>
            <Descriptions.Item label="So snapshot">{data?.snapshotCount ?? 0}</Descriptions.Item>
            <Descriptions.Item label="Dong bo luc">
              {data?.syncedAt ? new Date(data.syncedAt).toLocaleString() : "Chua co du lieu"}
            </Descriptions.Item>
          </Descriptions>
          <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
            Refresh
          </Button>
        </Space>
      </Card>
      <Card
        title="Danh gia tong quan"
        loading={loading}
        extra={
          editingAssessment ? (
            <Space>
              <Button
                onClick={() => {
                  setEditingAssessment(false);
                  setAssessmentDraft(assessmentToHtml(data?.overviewAssessment));
                  setEditorResetToken((prev) => prev + 1);
                  if (searchParams.get("editAssessment") === "1") {
                    searchParams.delete("editAssessment");
                    setSearchParams(searchParams, { replace: true });
                  }
                }}
              >
                Huy
              </Button>
              <Button type="primary" icon={<SaveOutlined />} onClick={() => void saveAssessment()} loading={savingAssessment}>
                Luu
              </Button>
            </Space>
          ) : (
            <Button
              icon={<EditOutlined />}
              onClick={() => {
                setEditingAssessment(true);
                setSearchParams((prev) => {
                  const next = new URLSearchParams(prev);
                  next.set("editAssessment", "1");
                  return next;
                }, { replace: true });
              }}
            >
              Viet danh gia
            </Button>
          )
        }
      >
        {editingAssessment ? (
          <RichTextEditor ref={editorRef} value={assessmentDraft} onChange={setAssessmentDraft} resetToken={editorResetToken} />
        ) : data?.overviewAssessment ? (
          <div
            style={{ lineHeight: 1.8 }}
            dangerouslySetInnerHTML={{ __html: assessmentToHtml(data.overviewAssessment) }}
          />
        ) : (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Chua co thong tin danh gia cho ticker nay." />
        )}
      </Card>
      {snapshots.length ? (
        snapshots.map((snapshot) => <SnapshotCard key={snapshot.id} snapshot={snapshot} />)
      ) : (
        <Card loading={loading}>
          <Empty description="Chua co du lieu chart cho ticker nay." />
        </Card>
      )}
    </Space>
  );
}
