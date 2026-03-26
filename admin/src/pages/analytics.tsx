import { Button, Card, Checkbox, Empty, Select, Space, Spin, Typography, message, theme as antdTheme } from "antd";
import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient, type ApiEnvelope } from "../lib/api";

type IndustryGroup = {
  id: number;
  name: string;
};

type StockSymbolItem = {
  ticker: string;
  industryGroupId: number | null;
  industryGroupName: string | null;
};

type AnalyticsPoint = {
  tradingDate: string;
  totalMatchVal: number;
  totalMatchVol: number;
  ma5Val: number;
  ma10Val: number;
  ma20Val: number;
  ma5Vol: number;
  ma10Vol: number;
  ma20Vol: number;
};

type AnalyticsSeries = {
  scope: "industry" | "ticker";
  label: string;
  points: AnalyticsPoint[];
};

type AllocationItem = {
  key: string | number | null;
  name: string;
  totalMatchVal: number;
  weightPct: number;
};

type AllocationPoint = {
  tradingDate: string;
  allocations: AllocationItem[];
};

type AllocationSeries = {
  topN: number;
  contextLabel?: string | null;
  legendNames: string[];
  points: AllocationPoint[];
};

type MetricType = "value" | "volume";
type TooltipPosition = { x: number; y: number };
type MaKey = "ma5" | "ma10" | "ma20" | "ma50";
const INDUSTRY_ALL_VALUE = -1;

const MA_OPTIONS: Array<{ label: string; value: MaKey }> = [
  { label: "MA5", value: "ma5" },
  { label: "MA10", value: "ma10" },
  { label: "MA20", value: "ma20" },
  { label: "MA50", value: "ma50" },
];

function calculateMovingAverage(values: number[], period: number) {
  const result: number[] = [];
  let sum = 0;
  for (let index = 0; index < values.length; index += 1) {
    sum += values[index];
    if (index >= period) {
      sum -= values[index - period];
    }
    const divisor = Math.min(index + 1, period);
    result.push(sum / divisor);
  }
  return result;
}

function sortAnalyticsPoints(points: AnalyticsPoint[]) {
  return [...points].sort((left, right) => left.tradingDate.localeCompare(right.tradingDate));
}

function trimLeadingLowSignalAnalyticsPoints(points: AnalyticsPoint[], metric: MetricType) {
  if (points.length < 4) {
    return points;
  }
  const values = points.map((point) => (metric === "value" ? point.totalMatchVal : point.totalMatchVol));
  const maxValue = Math.max(...values);
  if (maxValue <= 0) {
    return points;
  }
  const threshold = maxValue * 0.12;
  let startIndex = -1;
  for (let index = 0; index <= values.length - 3; index += 1) {
    if (values[index] >= threshold && values[index + 1] >= threshold && values[index + 2] >= threshold) {
      startIndex = index;
      break;
    }
  }
  if (startIndex <= 0) {
    return points;
  }
  return points.slice(startIndex);
}

function sortAllocationPoints(points: AllocationPoint[]) {
  return [...points].sort((left, right) => left.tradingDate.localeCompare(right.tradingDate));
}

function trimLeadingOtherOnlyPoints(points: AllocationPoint[]) {
  const startIndex = points.findIndex((point) =>
    point.allocations.some((item) => item.name !== "Khac" && item.weightPct > 0),
  );
  if (startIndex <= 0) {
    return points;
  }
  return points.slice(startIndex);
}

function trimLeadingLowSignalPoints(points: AllocationPoint[]) {
  const hasStrongSignal = (point: AllocationPoint) => {
    const nonOtherItems = point.allocations.filter((item) => item.name !== "Khac");
    const nonOtherTotal = nonOtherItems.reduce((sum, item) => sum + item.weightPct, 0);
    const majorItems = nonOtherItems.filter((item) => item.weightPct >= 8).length;
    return nonOtherTotal >= 35 && majorItems >= 2;
  };

  let startIndex = -1;
  for (let index = 0; index <= points.length - 3; index += 1) {
    if (hasStrongSignal(points[index]) && hasStrongSignal(points[index + 1]) && hasStrongSignal(points[index + 2])) {
      startIndex = index;
      break;
    }
  }
  if (startIndex <= 0) {
    return points;
  }
  return points.slice(startIndex);
}

function limitRecentPoints(points: AllocationPoint[], maxPoints?: number) {
  if (!maxPoints || points.length <= maxPoints) {
    return points;
  }
  return points.slice(points.length - maxPoints);
}

function getTooltipPosition({
  relativeX,
  relativeY,
  containerWidth,
  containerHeight,
  tooltipWidth,
  tooltipHeight,
}: {
  relativeX: number;
  relativeY: number;
  containerWidth: number;
  containerHeight: number;
  tooltipWidth: number;
  tooltipHeight: number;
}) {
  const gap = 12;
  const x = Math.max(8, Math.min(relativeX + gap, containerWidth - tooltipWidth - 8));
  const y = Math.max(8, Math.min(relativeY + gap, containerHeight - tooltipHeight - 8));
  return { x, y };
}

function formatDate(dateText: string) {
  const date = new Date(dateText);
  if (Number.isNaN(date.getTime())) {
    return dateText;
  }
  return `${String(date.getDate()).padStart(2, "0")}/${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function formatNumber(value: number) {
  return Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(value);
}

function resolveLegendNames(data?: { legendNames?: string[]; legends?: string[] } | null) {
  return data?.legendNames ?? data?.legends ?? [];
}

function resolveWeightPct(item?: { weightPct?: number; percentage?: number } | null) {
  return item?.weightPct ?? item?.percentage ?? 0;
}

function buildPath(points: number[], min: number, max: number, width: number, height: number) {
  if (points.length === 0) {
    return "";
  }
  const paddingX = 50;
  const paddingY = 24;
  const innerWidth = width - paddingX * 2;
  const innerHeight = height - paddingY * 2;
  const range = max - min || 1;

  return points
    .map((value, index) => {
      const x = paddingX + (index / Math.max(points.length - 1, 1)) * innerWidth;
      const y = paddingY + ((max - value) / range) * innerHeight;
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

function AnalyticsChart({
  title,
  series,
  metric,
  compactLeadingNoise = false,
  maxPoints,
  visibleMas,
}: {
  title: string;
  series: AnalyticsSeries | null;
  metric: MetricType;
  compactLeadingNoise?: boolean;
  maxPoints?: number;
  visibleMas: MaKey[];
}) {
  const { token } = antdTheme.useToken();
  const width = 980;
  const height = 300;
  const paddingX = 50;
  const paddingY = 24;
  const tooltipWidth = 220;
  const tooltipHeight = 112;
  const innerWidth = width - paddingX * 2;
  const sortedRows = sortAnalyticsPoints(series?.points ?? []);
  const trimmedRows = compactLeadingNoise ? trimLeadingLowSignalAnalyticsPoints(sortedRows, metric) : sortedRows;
  const rows = maxPoints && trimmedRows.length > maxPoints ? trimmedRows.slice(trimmedRows.length - maxPoints) : trimmedRows;
  const metricValues = rows.map((item) => (metric === "value" ? item.totalMatchVal : item.totalMatchVol));
  const maValues: Record<MaKey, number[]> = {
    ma5: calculateMovingAverage(metricValues, 5),
    ma10: calculateMovingAverage(metricValues, 10),
    ma20: calculateMovingAverage(metricValues, 20),
    ma50: calculateMovingAverage(metricValues, 50),
  };
  const allValues = [
    ...metricValues,
    ...visibleMas.flatMap((maKey) => maValues[maKey]),
  ];
  const min = allValues.length > 0 ? Math.min(...allValues) : 0;
  const max = allValues.length > 0 ? Math.max(...allValues) : 1;

  const rawPath = buildPath(metricValues, min, max, width, height);
  const maConfig: Array<{ key: MaKey; color: string; label: string }> = [
    { key: "ma5", color: "#7c3aed", label: "MA5" },
    { key: "ma10", color: "#16a34a", label: "MA10" },
    { key: "ma20", color: "#f97316", label: "MA20" },
    { key: "ma50", color: "#eab308", label: "MA50" },
  ];
  const visibleMaConfig = maConfig.filter((item) => visibleMas.includes(item.key));

  const xTicks = rows.filter((_, index) => index % Math.max(Math.floor(rows.length / 6), 1) === 0);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const hovered = hoveredIndex != null ? rows[hoveredIndex] : null;
  const hoveredX =
    hoveredIndex != null
      ? paddingX + (hoveredIndex / Math.max(rows.length - 1, 1)) * innerWidth
      : null;

  return (
    <Card size="small" title={title}>
      {rows.length === 0 ? (
        <Empty description="Khong co du lieu" />
      ) : (
        <>
          <Space size="middle" wrap style={{ marginBottom: 8 }}>
            <Typography.Text style={{ color: "#1677ff" }}>Gia tri/Vol thuc te</Typography.Text>
            {visibleMaConfig.map((item) => (
              <Typography.Text key={item.key} style={{ color: item.color }}>
                {item.label}
              </Typography.Text>
            ))}
          </Space>
          <div style={{ position: "relative" }}>
            <svg
              width="100%"
              height="320"
              viewBox={`0 0 ${width} ${height}`}
              role="img"
              aria-label={title}
              onMouseMove={(event) => {
                if (rows.length === 0) {
                  return;
                }
                const svg = event.currentTarget;
                const bounds = svg.getBoundingClientRect();
                const relativeX = event.clientX - bounds.left;
                const relativeY = event.clientY - bounds.top;
                const xInViewBox = (relativeX / bounds.width) * width;
                const normalized = Math.min(Math.max((xInViewBox - paddingX) / innerWidth, 0), 1);
                const index = Math.round(normalized * Math.max(rows.length - 1, 0));
                setHoveredIndex(index);
                setTooltipPosition(
                  getTooltipPosition({
                    relativeX,
                    relativeY,
                    containerWidth: bounds.width,
                    containerHeight: bounds.height,
                    tooltipWidth,
                    tooltipHeight,
                  }),
                );
              }}
              onMouseLeave={() => {
                setHoveredIndex(null);
                setTooltipPosition(null);
              }}
            >
              <rect x="0" y="0" width={width} height={height} fill="transparent" />
            <line x1="50" y1="276" x2="930" y2="276" stroke={token.colorBorder} strokeWidth="1.5" />
            <line x1="50" y1="24" x2="50" y2="276" stroke={token.colorBorder} strokeWidth="1.5" />
            <path d={rawPath} fill="none" stroke="#1677ff" strokeWidth="2.6" />
            {visibleMaConfig.map((item) => (
              <path
                key={item.key}
                d={buildPath(maValues[item.key], min, max, width, height)}
                fill="none"
                stroke={item.color}
                strokeWidth="2"
              />
            ))}
            {hoveredX != null ? (
              <line
                x1={hoveredX}
                y1={paddingY}
                x2={hoveredX}
                y2={height - paddingY}
                stroke={token.colorTextQuaternary}
                strokeWidth="1.25"
                strokeDasharray="4 4"
              />
            ) : null}

            {xTicks.map((item, index) => {
              const itemIndex = rows.findIndex((row) => row.tradingDate === item.tradingDate);
              const x = paddingX + (itemIndex / Math.max(rows.length - 1, 1)) * innerWidth;
              return (
                <text key={`${item.tradingDate}-${index}`} x={x} y={294} textAnchor="middle" fontSize="11" fill={token.colorTextSecondary}>
                  {formatDate(item.tradingDate)}
                </text>
              );
            })}

            <text x={44} y={32} textAnchor="end" fontSize="11" fill={token.colorTextSecondary}>
              {formatNumber(max)}
            </text>
            <text x={44} y={280} textAnchor="end" fontSize="11" fill={token.colorTextSecondary}>
              {formatNumber(min)}
            </text>
            </svg>
            {hovered && tooltipPosition ? (
              <div
                ref={containerRef}
                style={{
                  position: "absolute",
                  left: tooltipPosition.x,
                  top: tooltipPosition.y,
                  pointerEvents: "none",
                  background: token.colorBgElevated,
                  color: token.colorText,
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 8,
                  padding: "8px 10px",
                  width: tooltipWidth,
                  boxShadow: token.boxShadowSecondary,
                  fontSize: 12,
                  zIndex: 2,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{hovered.tradingDate}</div>
                <div>
                  Gia tri ngay:{" "}
                  <strong>{formatNumber(metric === "value" ? hovered.totalMatchVal : hovered.totalMatchVol)}</strong>
                </div>
                {visibleMaConfig.map((item) => (
                  <div key={item.key}>
                    {item.label}: {formatNumber(maValues[item.key][hoveredIndex ?? 0] ?? 0)}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </>
      )}
    </Card>
  );
}

function AllocationChart({
  data,
  title,
  ariaLabel,
  subtitle,
  compactLeadingNoise = false,
  maxPoints,
}: {
  data: AllocationSeries | null;
  title: string;
  ariaLabel: string;
  subtitle?: string | null;
  compactLeadingNoise?: boolean;
  maxPoints?: number;
}) {
  const { token } = antdTheme.useToken();
  const width = 980;
  const height = 420;
  const paddingLeft = 0;
  const paddingRight = 46;
  const paddingTop = 10;
  const paddingBottom = 78;
  const innerWidth = width - paddingLeft - paddingRight;
  const innerHeight = height - paddingTop - paddingBottom;
  const sortedPoints = trimLeadingOtherOnlyPoints(sortAllocationPoints(data?.points ?? []));
  const trimmedPoints = compactLeadingNoise ? trimLeadingLowSignalPoints(sortedPoints) : sortedPoints;
  const points = limitRecentPoints(trimmedPoints, maxPoints);
  const legends = data?.legendNames ?? [];
  const colorPalette = [
    "#1f6d8f",
    "#ff7124",
    "#1a7f24",
    "#20a8e0",
    "#b11aa9",
    "#58c21f",
    "#184f70",
    "#c46223",
    "#0f5a2d",
    "#1274b8",
    "#7a197f",
    "#5c7f36",
  ];
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition | null>(null);
  const tooltipWidth = 280;
  const tooltipHeight = 236;

  const legendToSeries = new Map<string, number[]>();
  legends.forEach((legend) => legendToSeries.set(legend, []));
  points.forEach((point) => {
    const map = new Map(point.allocations.map((item) => [item.name, item.weightPct]));
    legends.forEach((legend) => {
      legendToSeries.get(legend)?.push(map.get(legend) ?? 0);
    });
  });

  const xOfIndex = (index: number) => paddingLeft + (index / Math.max(points.length - 1, 1)) * innerWidth;
  const yFromPct = (pct: number) => paddingTop + ((100 - pct) / 100) * innerHeight;

  const cumulative = Array(points.length).fill(0);
  const stackedAreas = legends.map((legend, index) => {
    const values = legendToSeries.get(legend) ?? Array(points.length).fill(0);
    const lower = [...cumulative];
    const upper = values.map((value, idx) => {
      cumulative[idx] += value;
      return cumulative[idx];
    });

    const topLine = upper
      .map((value, idx) => `${idx === 0 ? "M" : "L"}${xOfIndex(idx).toFixed(2)} ${yFromPct(value).toFixed(2)}`)
      .join(" ");
    const bottomLine = lower
      .slice()
      .reverse()
      .map((value, reverseIdx) => {
        const idx = lower.length - 1 - reverseIdx;
        return `L${xOfIndex(idx).toFixed(2)} ${yFromPct(value).toFixed(2)}`;
      })
      .join(" ");

    return {
      legend,
      color: colorPalette[index % colorPalette.length],
      areaPath: `${topLine} ${bottomLine} Z`,
      linePath: topLine,
    };
  });

  const xTicks = points.filter((_, index) => index % Math.max(Math.floor(points.length / 6), 1) === 0);
  const hoveredPoint = hoveredIndex != null ? points[hoveredIndex] : null;
  const hoveredX =
    hoveredIndex != null
      ? paddingLeft + (hoveredIndex / Math.max(points.length - 1, 1)) * innerWidth
      : null;

  return (
    <Card size="small" title={title}>
      {points.length === 0 ? (
        <Empty description="Khong co du lieu phan bo nganh" />
      ) : (
        <>
          <Space wrap size={[12, 8]} style={{ marginBottom: 10 }}>
            {legends.map((legend, index) => (
              <div key={legend} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <span
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    background: colorPalette[index % colorPalette.length],
                    display: "inline-block",
                    flex: "0 0 auto",
                  }}
                />
                <Typography.Text type="secondary">{legend}</Typography.Text>
              </div>
            ))}
          </Space>
          {subtitle !== null ? (
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 14, minHeight: 22 }}>
              Nganh: <strong>{subtitle ?? data?.contextLabel ?? "Chua xac dinh"}</strong>
            </Typography.Text>
          ) : null}
          <div style={{ position: "relative" }}>
            <div style={{ overflowX: "auto", overflowY: "hidden" }}>
              <svg
                width="100%"
                height="430"
                viewBox={`0 0 ${width} ${height}`}
                role="img"
                aria-label={ariaLabel}
                onMouseMove={(event) => {
                  const svg = event.currentTarget;
                  const bounds = svg.getBoundingClientRect();
                  const relativeX = event.clientX - bounds.left;
                  const relativeY = event.clientY - bounds.top;
                  const xInViewBox = (relativeX / bounds.width) * width;
                  const normalized = Math.min(Math.max((xInViewBox - paddingLeft) / innerWidth, 0), 1);
                  const index = Math.round(normalized * Math.max(points.length - 1, 0));
                  setHoveredIndex(index);
                  setTooltipPosition(
                    getTooltipPosition({
                      relativeX,
                      relativeY,
                      containerWidth: bounds.width,
                      containerHeight: bounds.height,
                      tooltipWidth,
                      tooltipHeight,
                    }),
                  );
                }}
                onMouseLeave={() => {
                  setHoveredIndex(null);
                  setTooltipPosition(null);
                }}
              >
              <rect x="0" y="0" width={width} height={height} fill={token.colorBgContainer} />
              {[0, 20, 40, 60, 80, 100].map((pct) => {
                const y = paddingTop + ((100 - pct) / 100) * innerHeight;
                return (
                  <g key={pct}>
                    <line x1={paddingLeft} y1={y} x2={width - paddingRight} y2={y} stroke={token.colorBorder} strokeWidth="1" />
                    <text x={width - paddingRight + 10} y={y + 4} textAnchor="start" fontSize="11" fill={token.colorTextSecondary}>
                      {pct}%
                    </text>
                  </g>
                );
              })}
              {stackedAreas.map((layer) => (
                <path
                  key={`${layer.legend}-area`}
                  d={layer.areaPath}
                  fill={layer.color}
                  fillOpacity={1}
                  stroke="none"
                />
              ))}
              {hoveredX != null ? (
                <line
                  x1={hoveredX}
                  y1={paddingTop}
                  x2={hoveredX}
                  y2={height - paddingBottom}
                  stroke={token.colorWhite}
                  strokeWidth="1.2"
                  strokeDasharray="5 5"
                />
              ) : null}
              {xTicks.map((item, index) => {
                const itemIndex = points.findIndex((row) => row.tradingDate === item.tradingDate);
                const x = paddingLeft + (itemIndex / Math.max(points.length - 1, 1)) * innerWidth;
                return (
                  <text
                    key={`${item.tradingDate}-${index}`}
                    x={x}
                    y={height - 6}
                    textAnchor="end"
                    fontSize="11"
                    fill={token.colorTextSecondary}
                    transform={`rotate(-90 ${x} ${height - 6})`}
                  >
                    {formatDate(item.tradingDate)}
                  </text>
                );
              })}
              <line x1={paddingLeft} y1={height - paddingBottom} x2={width - paddingRight} y2={height - paddingBottom} stroke={token.colorBorder} />
            </svg>
            </div>
            {hoveredPoint && tooltipPosition ? (
              <div
                style={{
                  position: "absolute",
                  left: tooltipPosition.x,
                  top: tooltipPosition.y,
                  pointerEvents: "none",
                  background: token.colorBgElevated,
                  color: token.colorText,
                  border: `1px solid ${token.colorBorderSecondary}`,
                  borderRadius: 8,
                  padding: "8px 10px",
                  width: tooltipWidth,
                  boxShadow: token.boxShadowSecondary,
                  fontSize: 12,
                  zIndex: 2,
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: 4 }}>{hoveredPoint.tradingDate}</div>
                <div style={{ marginBottom: 6 }}>Tong: <strong>100%</strong></div>
                {hoveredPoint.allocations
                  .slice()
                  .sort((left, right) => right.weightPct - left.weightPct)
                  .map((item) => {
                    const colorIndex = legends.findIndex((legend) => legend === item.name);
                    const itemColor = colorPalette[(colorIndex >= 0 ? colorIndex : 0) % colorPalette.length];

                    return (
                      <div
                        key={`${hoveredPoint.tradingDate}-${item.name}`}
                        style={{ display: "flex", alignItems: "center", gap: 8 }}
                      >
                        <span
                          style={{
                            width: 10,
                            height: 10,
                            borderRadius: 2,
                            background: itemColor,
                            display: "inline-block",
                            flex: "0 0 auto",
                          }}
                        />
                        <span>
                          {item.name}: <strong>{formatNumber(item.weightPct)}%</strong> ({formatNumber(item.totalMatchVal)})
                        </span>
                      </div>
                    );
                  })}
              </div>
            ) : null}
          </div>
        </>
      )}
    </Card>
  );
}

export function AnalyticsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialIndustryGroupId = (() => {
    const value = searchParams.get("industryGroupId");
    if (!value) {
      return undefined;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
  })();
  const initialTicker = searchParams.get("ticker")?.trim().toUpperCase() || undefined;
  const [industryGroups, setIndustryGroups] = useState<IndustryGroup[]>([]);
  const [industryGroupId, setIndustryGroupId] = useState<number | undefined>(initialIndustryGroupId);
  const [tickers, setTickers] = useState<string[]>([]);
  const [ticker, setTicker] = useState<string | undefined>(initialTicker);
  const [loadingIndustryGroups, setLoadingIndustryGroups] = useState(false);
  const [loadingTickers, setLoadingTickers] = useState(false);
  const [loadingIndustryAnalytics, setLoadingIndustryAnalytics] = useState(false);
  const [loadingTickerAnalytics, setLoadingTickerAnalytics] = useState(false);
  const [loadingAllocationAnalytics, setLoadingAllocationAnalytics] = useState(false);
  const [loadingTickerAllocationAnalytics, setLoadingTickerAllocationAnalytics] = useState(false);

  const [industryAnalytics, setIndustryAnalytics] = useState<AnalyticsSeries | null>(null);
  const [tickerAnalytics, setTickerAnalytics] = useState<AnalyticsSeries | null>(null);
  const [industryAllocation, setIndustryAllocation] = useState<AllocationSeries | null>(null);
  const [tickerAllocation, setTickerAllocation] = useState<AllocationSeries | null>(null);
  const [industryVisibleMas, setIndustryVisibleMas] = useState<MaKey[]>(["ma20"]);
  const [tickerVisibleMas, setTickerVisibleMas] = useState<MaKey[]>(["ma20"]);
  const restoredIndustryRef = useRef(false);
  const restoredTickerRef = useRef(false);

  function updateSearch(next: { industryGroupId?: number; ticker?: string }) {
    const params = new URLSearchParams(searchParams);
    if (next.industryGroupId == null) {
      params.delete("industryGroupId");
    } else {
      params.set("industryGroupId", String(next.industryGroupId));
    }
    const normalizedTicker = next.ticker?.trim().toUpperCase() ?? "";
    if (!normalizedTicker) {
      params.delete("ticker");
    } else {
      params.set("ticker", normalizedTicker);
    }
    setSearchParams(params, { replace: true });
  }

  useEffect(() => {
    async function loadIndustryGroupsAndTickers() {
      setLoadingIndustryGroups(true);
      setLoadingTickers(true);
      try {
        const [industryRes, tickerRes] = await Promise.all([
          apiClient.get<ApiEnvelope<IndustryGroup[]>>("/admin/stocks/industry-groups"),
          apiClient.get<ApiEnvelope<string[]>>("/admin/stocks/tickers"),
        ]);
        setIndustryGroups(industryRes.data.data);
        setTickers(tickerRes.data.data);
      } finally {
        setLoadingIndustryGroups(false);
        setLoadingTickers(false);
      }
    }

    void loadIndustryGroupsAndTickers();
  }, []);

  useEffect(() => {
    if (restoredIndustryRef.current) {
      return;
    }
    restoredIndustryRef.current = true;
    if (initialIndustryGroupId != null) {
      restoredIndustryRef.current = true;
      void handleIndustryAnalytics();
      return;
    }
    void handleIndustryAnalytics();
  }, [initialIndustryGroupId]);

  useEffect(() => {
    if (!restoredTickerRef.current && initialTicker) {
      restoredTickerRef.current = true;
      void handleTickerAnalytics();
    }
  }, [initialTicker]);

  const selectedIndustryLabel = industryGroups.find((item) => item.id === industryGroupId)?.name ?? "Tat ca nganh";

  async function handleIndustryAnalytics(nextIndustryGroupId?: number) {
    setLoadingIndustryAnalytics(true);
    setLoadingAllocationAnalytics(true);
    try {
      updateSearch({ industryGroupId: nextIndustryGroupId, ticker });
      const [res, allocationRes] = await Promise.all([
        apiClient.get<ApiEnvelope<AnalyticsSeries>>("/admin/stocks/analytics/industry", {
          params: { industryGroupId: nextIndustryGroupId },
        }),
        apiClient.get<ApiEnvelope<{
          topN: number;
          legendNames?: string[];
          legends?: string[];
          points: Array<{
            tradingDate: string;
            allocations: Array<{
              industryGroupId: number | null;
              industryGroupName: string;
              totalMatchVal: number;
              weightPct?: number;
              percentage?: number;
            }>;
          }>;
        }>>("/admin/stocks/analytics/industry-allocation", {
          params: { topN: 5 },
        }),
      ]);
      setIndustryAnalytics(res.data.data);
      setIndustryAllocation({
        topN: allocationRes.data.data.topN,
        contextLabel: null,
        legendNames: resolveLegendNames(allocationRes.data.data),
        points: allocationRes.data.data.points.map((point) => ({
          tradingDate: point.tradingDate,
          allocations: point.allocations.map((item) => ({
            key: item.industryGroupId,
            name: item.industryGroupName,
            totalMatchVal: item.totalMatchVal,
            weightPct: resolveWeightPct(item),
          })),
        })),
      });
    } finally {
      setLoadingIndustryAnalytics(false);
      setLoadingAllocationAnalytics(false);
    }
  }

  async function handleTickerAnalytics(nextTicker?: string) {
    const normalizedTicker = nextTicker?.trim().toUpperCase() ?? ticker?.trim().toUpperCase() ?? "";
    if (!normalizedTicker) {
      return;
    }
    setLoadingTickerAnalytics(true);
    setLoadingTickerAllocationAnalytics(true);
    try {
      if (normalizedTicker !== ticker) {
        setTicker(normalizedTicker);
      }
      updateSearch({ industryGroupId, ticker: normalizedTicker });
      const [analyticsResult, allocationResult] = await Promise.allSettled([
        apiClient.get<ApiEnvelope<AnalyticsSeries>>("/admin/stocks/analytics/ticker", {
          params: { ticker: normalizedTicker },
        }),
        apiClient.get<ApiEnvelope<{
          topN: number;
          industryLabel: string | null;
          legendNames?: string[];
          legends?: string[];
          points: Array<{
            tradingDate: string;
            allocations: Array<{
              ticker: string;
              totalMatchVal: number;
              weightPct?: number;
              percentage?: number;
            }>;
          }>;
        }>>("/admin/stocks/analytics/ticker-allocation", {
          params: { ticker: normalizedTicker, topN: 8 },
        }),
      ]);

      if (analyticsResult.status === "fulfilled") {
        setTickerAnalytics(analyticsResult.value.data.data);
      } else {
        throw analyticsResult.reason;
      }

      if (allocationResult.status === "fulfilled") {
        let resolvedIndustryLabel = allocationResult.value.data.data.industryLabel;
        if (!resolvedIndustryLabel) {
          try {
            const stockRes = await apiClient.get<ApiEnvelope<{
              items: StockSymbolItem[];
              page: number;
              size: number;
              totalElements: number;
              totalPages: number;
            }>>("/admin/stocks", {
              params: { ticker: normalizedTicker, page: 0, size: 1 },
            });
            const matched = stockRes.data.data.items.find((item) => item.ticker?.toUpperCase() === normalizedTicker);
            if (matched?.industryGroupName) {
              resolvedIndustryLabel = matched.industryGroupId != null
                ? `${matched.industryGroupName} (#${matched.industryGroupId})`
                : matched.industryGroupName;
            }
          } catch {
            // Keep the backend label when available and silently skip metadata fallback failures.
          }
        }

        setTickerAllocation({
          topN: allocationResult.value.data.data.topN,
          contextLabel: resolvedIndustryLabel,
          legendNames: resolveLegendNames(allocationResult.value.data.data),
          points: allocationResult.value.data.data.points.map((point) => ({
            tradingDate: point.tradingDate,
            allocations: point.allocations.map((item) => ({
              key: item.ticker,
              name: item.ticker,
              totalMatchVal: item.totalMatchVal,
              weightPct: resolveWeightPct(item),
            })),
          })),
        });
      } else {
        setTickerAllocation(null);
        message.warning("Chua tai duoc chart ty trong theo ticker, nhung du lieu ticker chinh van da hien.");
      }
    } catch {
      setTickerAnalytics(null);
      setTickerAllocation(null);
      message.error("Khong tai duoc du lieu ticker.");
    } finally {
      setLoadingTickerAnalytics(false);
      setLoadingTickerAllocationAnalytics(false);
    }
  }

  async function handleClearIndustryFilter() {
    setIndustryGroupId(undefined);
    updateSearch({ industryGroupId: undefined, ticker });
    setIndustryAnalytics(null);
    setIndustryAllocation(null);
    setLoadingIndustryAnalytics(true);
    setLoadingAllocationAnalytics(true);
    try {
      const [res, allocationRes] = await Promise.all([
        apiClient.get<ApiEnvelope<AnalyticsSeries>>("/admin/stocks/analytics/industry"),
        apiClient.get<ApiEnvelope<{
          topN: number;
          legendNames?: string[];
          legends?: string[];
          points: Array<{
            tradingDate: string;
            allocations: Array<{
              industryGroupId: number | null;
              industryGroupName: string;
              totalMatchVal: number;
              weightPct?: number;
              percentage?: number;
            }>;
          }>;
        }>>("/admin/stocks/analytics/industry-allocation", {
          params: { topN: 5 },
        }),
      ]);
      setIndustryAnalytics(res.data.data);
      setIndustryAllocation({
        topN: allocationRes.data.data.topN,
        contextLabel: null,
        legendNames: resolveLegendNames(allocationRes.data.data),
        points: allocationRes.data.data.points.map((point) => ({
          tradingDate: point.tradingDate,
          allocations: point.allocations.map((item) => ({
            key: item.industryGroupId,
            name: item.industryGroupName,
            totalMatchVal: item.totalMatchVal,
            weightPct: resolveWeightPct(item),
          })),
        })),
      });
    } finally {
      setLoadingIndustryAnalytics(false);
      setLoadingAllocationAnalytics(false);
    }
  }

  function handleClearTickerFilter() {
    setTicker(undefined);
    updateSearch({ industryGroupId, ticker: undefined });
    setTickerAnalytics(null);
    setTickerAllocation(null);
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3}>Tong hop so lieu</Typography.Title>

      <Card title="Tong hop theo nganh">
        <Space wrap>
          <Select<number>
            loading={loadingIndustryGroups}
            placeholder="Chon nhom nganh"
            value={industryGroupId ?? INDUSTRY_ALL_VALUE}
            onChange={(value) => {
              const nextIndustryGroupId = value === INDUSTRY_ALL_VALUE ? undefined : value;
              setIndustryGroupId(nextIndustryGroupId);
              updateSearch({ industryGroupId: nextIndustryGroupId, ticker });
              void handleIndustryAnalytics(nextIndustryGroupId);
            }}
            options={[
              { value: INDUSTRY_ALL_VALUE, label: "Tat ca nhom nganh" },
              ...industryGroups.map((item) => ({ value: item.id, label: `${item.name} (#${item.id})` })),
            ]}
            style={{ minWidth: 320 }}
          />
          <Button type="primary" onClick={() => void handleIndustryAnalytics(industryGroupId)} loading={loadingIndustryAnalytics}>
            Tong hop
          </Button>
          <Button onClick={() => void handleClearIndustryFilter()}>Clear</Button>
        </Space>

        {industryAnalytics ? (
          <div style={{ marginTop: 16 }}>
            {loadingIndustryAnalytics ? (
              <Spin />
            ) : (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Checkbox.Group
                  options={MA_OPTIONS}
                  value={industryVisibleMas}
                  onChange={(values) => setIndustryVisibleMas(values as MaKey[])}
                />
                <AnalyticsChart
                  title={`Gia tri giao dich theo nganh: ${selectedIndustryLabel}`}
                  series={industryAnalytics}
                  metric="value"
                  compactLeadingNoise
                  maxPoints={60}
                  visibleMas={industryVisibleMas}
                />
                <AnalyticsChart
                  title={`Khoi luong giao dich theo nganh: ${selectedIndustryLabel}`}
                  series={industryAnalytics}
                  metric="volume"
                  compactLeadingNoise
                  maxPoints={60}
                  visibleMas={industryVisibleMas}
                />
                {loadingAllocationAnalytics ? (
                  <Spin />
                ) : (
                  <AllocationChart
                    data={industryAllocation}
                    title="Ty trong dong tien theo tung nganh (%)"
                    ariaLabel="Industry allocation over time"
                    subtitle={null}
                    compactLeadingNoise
                    maxPoints={60}
                  />
                )}
              </Space>
            )}
          </div>
        ) : null}
      </Card>

      <Card title="Tong hop theo ticker">
        <Space wrap>
          <Select<string>
            showSearch
            allowClear
            loading={loadingTickers}
            placeholder="Chon ticker (VD: HPG)"
            value={ticker}
            onChange={(value) => {
              const normalizedTicker = value?.trim().toUpperCase();
              setTicker(normalizedTicker);
              updateSearch({ industryGroupId, ticker: normalizedTicker });
              if (normalizedTicker) {
                void handleTickerAnalytics(normalizedTicker);
              } else {
                setTickerAnalytics(null);
                setTickerAllocation(null);
              }
            }}
            options={tickers.map((item) => ({ value: item, label: item }))}
            optionFilterProp="label"
            style={{ minWidth: 320 }}
          />
          <Button
            type="primary"
            onClick={() => void handleTickerAnalytics(ticker)}
            disabled={!ticker?.trim()}
            loading={loadingTickerAnalytics}
          >
            Tong hop
          </Button>
          <Button onClick={handleClearTickerFilter} disabled={!ticker && !tickerAnalytics && !tickerAllocation}>
            Clear
          </Button>
        </Space>

        {tickerAnalytics ? (
          <div style={{ marginTop: 16 }}>
            {loadingTickerAnalytics ? (
              <Spin />
            ) : (
              <Space direction="vertical" style={{ width: "100%" }} size="middle">
                <Checkbox.Group
                  options={MA_OPTIONS}
                  value={tickerVisibleMas}
                  onChange={(values) => setTickerVisibleMas(values as MaKey[])}
                />
                <AnalyticsChart
                  title={`Gia tri giao dich theo ticker: ${tickerAnalytics.label}`}
                  series={tickerAnalytics}
                  metric="value"
                  visibleMas={tickerVisibleMas}
                />
                <AnalyticsChart
                  title={`Khoi luong giao dich theo ticker: ${tickerAnalytics.label}`}
                  series={tickerAnalytics}
                  metric="volume"
                  visibleMas={tickerVisibleMas}
                />
                {loadingTickerAllocationAnalytics ? (
                  <Spin />
                ) : (
                  <AllocationChart
                    data={tickerAllocation}
                    title="Ty trong dong tien theo tung ticker (%)"
                    ariaLabel="Ticker allocation over time"
                    subtitle={tickerAllocation?.contextLabel}
                  />
                )}
              </Space>
            )}
          </div>
        ) : null}
      </Card>
    </Space>
  );
}
