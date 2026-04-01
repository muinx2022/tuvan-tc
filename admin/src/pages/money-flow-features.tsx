import {
  Alert,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Segmented,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Tabs,
  Typography,
  message,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs, { type Dayjs } from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type EntityType = "stock" | "sector" | "market";
type WindowType = "slot" | "eod";
type QuickFilter = "all" | "positive" | "negative" | "low_confidence";

type IndustryGroup = {
  id: number;
  name: string;
};

type MoneyFlowFeatureRow = {
  id: number;
  entityType: EntityType;
  entityId: string;
  tradingDate: string;
  windowType: WindowType;
  snapshotSlot: string | null;
  asOfAt: string | null;
  historyDaysUsed: number;
  historyBaselineDays: number;
  historyMinDaysForStable: number;
  lowHistoryConfidence: boolean;
  features: Record<string, unknown>;
  updatedAt: string | null;
};

type MoneyFlowFeaturePage = {
  items: MoneyFlowFeatureRow[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

type RebuildResponse = {
  tradingDate: string;
  slot?: {
    tradingDate: string;
    snapshotSlot: string;
    stocks: number;
    sectors: number;
  } | null;
  eod?: {
    tradingDate: string;
    stocks: number;
    sectors: number;
  } | null;
};

type T0SnapshotSlotsResponse = {
  tradingDate: string;
  slots: string[];
};

type BackfillEodResponse = {
  tradingDateFrom: string | null;
  tradingDateTo: string | null;
  dates: Array<{
    tradingDate: string;
    dailyCloseCount: number;
    stockCount: number;
    sectorCount: number;
  }>;
  totalDates: number;
  totalDailyClose: number;
  totalStocks: number;
  totalSectors: number;
};

type BackfillSlotResponse = {
  tradingDateFrom: string | null;
  tradingDateTo: string | null;
  dates: Array<{
    tradingDate: string;
    slots: Array<{
      snapshotSlot: string;
      stockCount: number;
      sectorCount: number;
    }>;
    slotCount: number;
  }>;
  totalDates: number;
  totalSlots: number;
  totalStocks: number;
  totalSectors: number;
};

function toNumber(value: unknown): number | null {
  if (value == null || value === "") {
    return null;
  }
  const num = typeof value === "string" ? Number(value) : Number(value);
  return Number.isFinite(num) ? num : null;
}

function formatNumber(value: unknown, digits = 2) {
  const num = toNumber(value);
  if (num == null) {
    return "-";
  }
  return Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(num);
}

function formatRatio(value: unknown) {
  return formatNumber(value, 4);
}

function ratioColor(value: unknown) {
  const num = toNumber(value);
  if (num == null) {
    return "default";
  }
  if (num >= 0.5) {
    return "green";
  }
  if (num > 0) {
    return "cyan";
  }
  if (num <= -0.5) {
    return "red";
  }
  if (num < 0) {
    return "volcano";
  }
  return "default";
}

function netFlowTextType(value: unknown): "success" | "danger" | undefined {
  const num = toNumber(value);
  if (num == null || num === 0) {
    return undefined;
  }
  return num > 0 ? "success" : "danger";
}

function renderMetricTag(value: unknown, formatter: (next: unknown) => string = formatRatio) {
  const num = toNumber(value);
  if (num == null) {
    return <Typography.Text type="secondary">-</Typography.Text>;
  }
  const prefix = num > 0 ? "+" : "";
  return <Tag color={ratioColor(num)}>{`${prefix}${formatter(num)}`}</Tag>;
}

function formatPercent(value: unknown) {
  const num = toNumber(value);
  if (num == null) {
    return "-";
  }
  return `${(num * 100).toFixed(2)}%`;
}

function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return dayjs(value).format("DD/MM/YYYY HH:mm:ss");
}

function formatEntityLabel(row: MoneyFlowFeatureRow, industriesById: Map<number, string>) {
  if (row.entityType === "stock") {
    const industryId = toNumber(row.features.industryGroupId);
    if (industryId && industriesById.has(industryId)) {
      return `${row.entityId} · ${industriesById.get(industryId)}`;
    }
    return row.entityId;
  }
  if (row.entityType === "sector") {
    const industryId = toNumber(row.features.industryGroupId) ?? Number(row.entityId);
    return industriesById.get(industryId) ?? `Nhom nganh #${row.entityId}`;
  }
  return "Market Global";
}

function getValue(row: MoneyFlowFeatureRow, slotKey: string, eodKey: string) {
  return row.windowType === "slot" ? row.features[slotKey] : row.features[eodKey];
}

function getNetFlowValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "netFlowVal", "netFlowValEod");
  }
  if (row.entityType === "sector") {
    return getValue(row, "sectorNetFlowVal", "sectorNetFlowValEod");
  }
  return getValue(row, "marketNetFlowVal", "marketNetFlowValEod");
}

function getActiveNetShareValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "activeNetShare", "activeNetShareEod");
  }
  if (row.entityType === "sector") {
    return getValue(row, "sectorActiveNetShare", "sectorActiveNetShareEod");
  }
  return getValue(row, "marketActiveNetShare", "marketActiveNetShareEod");
}

function getNetFlowRatioValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "netFlowRatioSlot", "netFlowRatioEod");
  }
  if (row.entityType === "sector") {
    return getValue(row, "sectorNetFlowRatioSlot", "sectorNetFlowRatioEod");
  }
  return getValue(row, "marketNetFlowRatioGlobalSlot", "marketNetFlowRatioGlobalEod");
}

function getVsMarketStrengthValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "stockVsMarketStrengthSlot", "stockVsMarketStrengthEod");
  }
  if (row.entityType === "sector") {
    return getValue(row, "sectorVsMarketStrengthSlot", "sectorVsMarketStrengthEod");
  }
  return null;
}

function getVsSectorStrengthValue(row: MoneyFlowFeatureRow) {
  if (row.entityType !== "stock") {
    return null;
  }
  return getValue(row, "stockVsSectorStrengthSlot", "stockVsSectorStrengthEod");
}

function getMarketRankValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "market") {
    return null;
  }
  return getValue(row, "marketStrengthRankSlot", "marketStrengthRankEod");
}

function getSectorRankValue(row: MoneyFlowFeatureRow) {
  if (row.entityType !== "stock") {
    return null;
  }
  return getValue(row, "sectorLeadershipRankSlot", "sectorLeadershipRankEod");
}

function getAvgAbsBaselineValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "avgAbsNetFlowHistSlot", "avgAbsNetFlowHistEod");
  }
  return null;
}

function getAvgShareBaselineValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "avgActiveNetShareHistSlot", "avgActiveNetShareHistEod");
  }
  return null;
}

function getShareDeltaValue(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return getValue(row, "activeNetShareDeltaSlot", "activeNetShareDeltaEod");
  }
  return null;
}

function primarySortMetric(row: MoneyFlowFeatureRow) {
  if (row.entityType === "stock") {
    return toNumber(getVsMarketStrengthValue(row)) ?? toNumber(getNetFlowRatioValue(row)) ?? Number.NEGATIVE_INFINITY;
  }
  if (row.entityType === "sector") {
    return toNumber(getVsMarketStrengthValue(row)) ?? toNumber(getNetFlowRatioValue(row)) ?? Number.NEGATIVE_INFINITY;
  }
  return toNumber(getNetFlowRatioValue(row)) ?? Number.NEGATIVE_INFINITY;
}

function secondarySortMetric(row: MoneyFlowFeatureRow) {
  return toNumber(getNetFlowValue(row)) ?? Number.NEGATIVE_INFINITY;
}

export function MoneyFlowFeaturesPage() {
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [backfillingEod, setBackfillingEod] = useState(false);
  const [backfillingSlot, setBackfillingSlot] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rows, setRows] = useState<MoneyFlowFeatureRow[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [entityType, setEntityType] = useState<EntityType>("stock");
  const [windowType, setWindowType] = useState<WindowType>("slot");
  const [tradingDate, setTradingDate] = useState(dayjs());
  const [snapshotSlot, setSnapshotSlot] = useState<string | undefined>(undefined);
  const [tickerFilter, setTickerFilter] = useState("");
  const [sectorFilter, setSectorFilter] = useState<number | undefined>(undefined);
  const [industries, setIndustries] = useState<IndustryGroup[]>([]);
  const [selectedRow, setSelectedRow] = useState<MoneyFlowFeatureRow | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [slotOptions, setSlotOptions] = useState<string[]>([]);
  const [backfillRange, setBackfillRange] = useState<[Dayjs | null, Dayjs | null] | null>(null);
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("all");

  const industriesById = useMemo(() => new Map(industries.map((item) => [item.id, item.name])), [industries]);

  const visibleEntityId = useMemo(() => {
    if (entityType === "stock") {
      return tickerFilter.trim().toUpperCase() || undefined;
    }
    if (entityType === "sector") {
      return sectorFilter != null ? String(sectorFilter) : undefined;
    }
    return "GLOBAL";
  }, [entityType, sectorFilter, tickerFilter]);

  const summary = useMemo(() => {
    const netValues = rows.map((row) => toNumber(getNetFlowValue(row)) ?? 0);
    const positive = netValues.filter((value) => value > 0).length;
    const negative = netValues.filter((value) => value < 0).length;
    return {
      totalNetFlow: netValues.reduce((sum, value) => sum + value, 0),
      positive,
      negative,
      lowConfidence: rows.filter((row) => row.lowHistoryConfidence).length,
    };
  }, [rows]);

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      const netFlow = toNumber(getNetFlowValue(row)) ?? 0;
      if (quickFilter === "positive") {
        return netFlow > 0;
      }
      if (quickFilter === "negative") {
        return netFlow < 0;
      }
      if (quickFilter === "low_confidence") {
        return row.lowHistoryConfidence;
      }
      return true;
    });
  }, [quickFilter, rows]);

  const sortedRows = useMemo(() => {
    return [...filteredRows].sort((left, right) => {
      const primaryDiff = primarySortMetric(right) - primarySortMetric(left);
      if (primaryDiff !== 0) {
        return primaryDiff;
      }
      return secondarySortMetric(right) - secondarySortMetric(left);
    });
  }, [filteredRows]);

  const allSortedRows = useMemo(() => {
    return [...rows].sort((left, right) => {
      const primaryDiff = primarySortMetric(right) - primarySortMetric(left);
      if (primaryDiff !== 0) {
        return primaryDiff;
      }
      return secondarySortMetric(right) - secondarySortMetric(left);
    });
  }, [rows]);

  const displayRows = useMemo(() => (sortedRows.length ? sortedRows : allSortedRows), [allSortedRows, sortedRows]);
  const heatmapRows = useMemo(() => displayRows.slice(0, 8), [displayRows]);

  async function load(
    page = 1,
    pageSize = pagination.pageSize,
    nextFilters?: {
      entityType?: EntityType;
      windowType?: WindowType;
      tradingDate?: string;
      snapshotSlot?: string | undefined;
      entityId?: string | undefined;
    },
  ) {
    const resolvedEntityType = nextFilters?.entityType ?? entityType;
    const resolvedWindowType = nextFilters?.windowType ?? windowType;
    const resolvedTradingDate = nextFilters?.tradingDate ?? tradingDate.format("YYYY-MM-DD");
    const resolvedSnapshotSlot = nextFilters?.snapshotSlot !== undefined ? nextFilters.snapshotSlot : snapshotSlot;
    const resolvedEntityId = nextFilters?.entityId !== undefined ? nextFilters.entityId : visibleEntityId;
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<ApiEnvelope<MoneyFlowFeaturePage>>("/admin/stocks/money-flow-features", {
        params: {
          page: page - 1,
          size: pageSize,
          entityType: resolvedEntityType,
          entityId: resolvedEntityId,
          tradingDate: resolvedTradingDate,
          windowType: resolvedWindowType,
          snapshotSlot: resolvedWindowType === "slot" ? resolvedSnapshotSlot : undefined,
        },
      });
      const data = res.data.data;
      setRows(data.items);
      setPagination({
        current: data.page + 1,
        pageSize: data.size,
        total: data.totalElements,
      });
    } catch (caught) {
      console.error(caught);
      setRows([]);
      setError("Khong tai duoc danh sach money flow features.");
    } finally {
      setLoading(false);
    }
  }

  async function loadIndustryGroups() {
    try {
      const res = await apiClient.get<ApiEnvelope<IndustryGroup[]>>("/admin/stocks/industry-groups");
      setIndustries(res.data.data);
    } catch {
      message.error("Khong tai duoc danh sach nhom nganh");
    }
  }

  async function loadSlotOptions(nextTradingDate = tradingDate.format("YYYY-MM-DD")) {
    try {
      const res = await apiClient.get<ApiEnvelope<T0SnapshotSlotsResponse>>("/admin/stocks/t0-snapshot-slots", {
        params: { tradingDate: nextTradingDate },
      });
      const slots = res.data.data.slots;
      setSlotOptions(slots);
      if (slots.length) {
        setSnapshotSlot((current) => (current && slots.includes(current) ? current : slots[slots.length - 1]));
      } else {
        setSnapshotSlot(undefined);
      }
    } catch {
      setSlotOptions([]);
      setSnapshotSlot(undefined);
    }
  }

  async function rebuildFeatures() {
    setRebuilding(true);
    try {
      const res = await apiClient.post<ApiEnvelope<RebuildResponse>>("/admin/stocks/money-flow-features/rebuild", {
        tradingDate: tradingDate.format("YYYY-MM-DD"),
        snapshotSlot: windowType === "slot" ? snapshotSlot : undefined,
        includeEod: true,
      });
      const payload = res.data.data;
      const slotMessage = payload.slot ? `slot ${payload.slot.snapshotSlot}: ${payload.slot.stocks} ma / ${payload.slot.sectors} sector` : "";
      const eodMessage = payload.eod ? `EOD: ${payload.eod.stocks} ma / ${payload.eod.sectors} sector` : "";
      message.success(["Da rebuild money flow", slotMessage, eodMessage].filter(Boolean).join(" | "));
      await load(1, pagination.pageSize);
    } catch (caught) {
      console.error(caught);
      message.error("Khong rebuild duoc money flow features.");
    } finally {
      setRebuilding(false);
    }
  }

  async function backfillEodHistory() {
    setBackfillingEod(true);
    try {
      const res = await apiClient.post<ApiEnvelope<BackfillEodResponse>>("/admin/stocks/money-flow-features/backfill-eod", {
        tradingDateFrom: backfillRange?.[0]?.format("YYYY-MM-DD"),
        tradingDateTo: backfillRange?.[1]?.format("YYYY-MM-DD"),
      });
      const payload = res.data.data;
      message.success(
        `Da backfill EOD cho ${payload.totalDates} ngay | daily close: ${payload.totalDailyClose} | stocks: ${payload.totalStocks} | sectors: ${payload.totalSectors}`,
      );
      if (windowType === "eod") {
        await load(1, pagination.pageSize);
      }
    } catch (caught) {
      console.error(caught);
      message.error("Khong backfill duoc EOD history.");
    } finally {
      setBackfillingEod(false);
    }
  }

  async function backfillSlotHistory() {
    setBackfillingSlot(true);
    try {
      const res = await apiClient.post<ApiEnvelope<BackfillSlotResponse>>("/admin/stocks/money-flow-features/backfill-slot", {
        tradingDateFrom: backfillRange?.[0]?.format("YYYY-MM-DD"),
        tradingDateTo: backfillRange?.[1]?.format("YYYY-MM-DD"),
      });
      const payload = res.data.data;
      message.success(
        `Da backfill intraday cho ${payload.totalDates} ngay | slots: ${payload.totalSlots} | stocks: ${payload.totalStocks} | sectors: ${payload.totalSectors}`,
      );
      if (windowType === "slot") {
        await load(1, pagination.pageSize);
      }
    } catch (caught) {
      console.error(caught);
      message.error("Khong backfill duoc intraday slot history.");
    } finally {
      setBackfillingSlot(false);
    }
  }

  function resetFilters() {
    const today = dayjs();
    setEntityType("stock");
    setWindowType("slot");
    setTradingDate(today);
    setSnapshotSlot(undefined);
    setTickerFilter("");
    setSectorFilter(undefined);
    void load(1, pagination.pageSize, {
      entityType: "stock",
      windowType: "slot",
      tradingDate: today.format("YYYY-MM-DD"),
      snapshotSlot: undefined,
      entityId: undefined,
    });
  }

  useEffect(() => {
    void loadIndustryGroups();
    void loadSlotOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (windowType !== "slot") {
      return;
    }
    const nextDate = tradingDate.format("YYYY-MM-DD");
    void loadSlotOptions(nextDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradingDate, windowType]);

  useEffect(() => {
    void load(1, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setPagination((current) => ({ ...current, current: 1 }));
    if (windowType === "slot" && !snapshotSlot) {
      return;
    }
    void load(1, pagination.pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entityType, windowType, snapshotSlot, tradingDate, visibleEntityId]);

  useEffect(() => {
    setQuickFilter("all");
  }, [windowType, snapshotSlot, tradingDate]);

  const columns: ColumnsType<MoneyFlowFeatureRow> = useMemo(() => {
    const shared: ColumnsType<MoneyFlowFeatureRow> = [
      {
        title: entityType === "stock" ? "Ma" : entityType === "sector" ? "Sector" : "Market",
        width: 220,
        render: (_: unknown, row) => <Typography.Text strong>{formatEntityLabel(row, industriesById)}</Typography.Text>,
      },
      {
        title: "Ngay",
        dataIndex: "tradingDate",
        width: 120,
      },
      {
        title: windowType === "slot" ? "Slot" : "Window",
        width: 100,
        render: (_: unknown, row) =>
          row.windowType === "slot"
            ? (row.snapshotSlot ? <Tag color="blue">{row.snapshotSlot}</Tag> : <Tag>-</Tag>)
            : <Tag color="gold">EOD</Tag>,
      },
      {
        title: "Net flow",
        align: "right",
        width: 140,
        render: (_: unknown, row) => (
          <Typography.Text type={netFlowTextType(getNetFlowValue(row))}>{formatNumber(getNetFlowValue(row))}</Typography.Text>
        ),
      },
      {
        title: "Active net share",
        align: "right",
        width: 130,
        render: (_: unknown, row) => renderMetricTag(getActiveNetShareValue(row), formatPercent),
      },
      {
        title: "Net flow ratio",
        align: "right",
        width: 130,
        render: (_: unknown, row) => renderMetricTag(getNetFlowRatioValue(row)),
      },
    ];

    if (entityType !== "market") {
      shared.push({
        title: "Vs market",
        align: "right",
        width: 120,
        render: (_: unknown, row) => renderMetricTag(getVsMarketStrengthValue(row)),
      });
      shared.push({
        title: "Rank market",
        align: "right",
        width: 110,
        render: (_: unknown, row) => formatNumber(getMarketRankValue(row), 0),
      });
    }

    if (entityType === "stock") {
      shared.push({
        title: "Vs sector",
        align: "right",
        width: 120,
        render: (_: unknown, row) => renderMetricTag(getVsSectorStrengthValue(row)),
      });
      shared.push({
        title: "Rank sector",
        align: "right",
        width: 110,
        render: (_: unknown, row) => formatNumber(getSectorRankValue(row), 0),
      });
      shared.push({
        title: "Baseline",
        align: "right",
        width: 140,
        render: (_: unknown, row) => formatNumber(getAvgAbsBaselineValue(row)),
      });
      shared.push({
        title: "Share baseline",
        align: "right",
        width: 140,
        render: (_: unknown, row) => renderMetricTag(getAvgShareBaselineValue(row), formatPercent),
      });
      shared.push({
        title: "Share delta",
        align: "right",
        width: 120,
        render: (_: unknown, row) => renderMetricTag(getShareDeltaValue(row), formatPercent),
      });
    }

    shared.push({
      title: "History",
      width: 120,
      render: (_: unknown, row) => (
        <Space direction="vertical" size={0}>
          <Typography.Text>{`${row.historyDaysUsed}/${row.historyBaselineDays}`}</Typography.Text>
          {row.lowHistoryConfidence ? <Tag color="orange">Low confidence</Tag> : <Tag color="green">On dinh</Tag>}
        </Space>
      ),
    });
    shared.push({
      title: "As of",
      width: 170,
      render: (_: unknown, row) => formatDateTime(row.asOfAt),
    });
    return shared;
  }, [entityType, industriesById, windowType]);

  const drawerDescriptions = useMemo(() => {
    if (!selectedRow) {
      return [];
    }
    return [
      { key: "entity", label: "Entity", children: formatEntityLabel(selectedRow, industriesById) },
      { key: "date", label: "Ngay", children: selectedRow.tradingDate },
      { key: "window", label: "Window", children: selectedRow.windowType === "slot" ? selectedRow.snapshotSlot ?? "-" : "EOD" },
      { key: "netFlow", label: "Net flow", children: formatNumber(getNetFlowValue(selectedRow)) },
      { key: "activeShare", label: "Active net share", children: formatPercent(getActiveNetShareValue(selectedRow)) },
      { key: "ratio", label: "Net flow ratio", children: formatRatio(getNetFlowRatioValue(selectedRow)) },
      { key: "vsMarket", label: "Vs market", children: formatRatio(getVsMarketStrengthValue(selectedRow)) },
      { key: "vsSector", label: "Vs sector", children: formatRatio(getVsSectorStrengthValue(selectedRow)) },
      { key: "rankMarket", label: "Rank market", children: formatNumber(getMarketRankValue(selectedRow), 0) },
      { key: "rankSector", label: "Rank sector", children: formatNumber(getSectorRankValue(selectedRow), 0) },
      { key: "history", label: "History days", children: `${selectedRow.historyDaysUsed}/${selectedRow.historyBaselineDays}` },
      { key: "confidence", label: "Confidence", children: selectedRow.lowHistoryConfidence ? "Low history confidence" : "On dinh" },
      { key: "updated", label: "Cap nhat", children: formatDateTime(selectedRow.updatedAt) },
    ];
  }, [industriesById, selectedRow]);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <div>
        <Typography.Title level={3} style={{ marginBottom: 0 }}>
          Money Flow Features
        </Typography.Title>
        <Typography.Text type="secondary">
          Theo doi bien raw, derived va market strength theo ma, sector va market. Intraday dung same-slot baseline, EOD dung full-day baseline.
        </Typography.Text>
      </div>

      <Card>
        <Tabs
          activeKey={entityType}
          onChange={(value) => {
            setEntityType(value as EntityType);
            setQuickFilter("all");
          }}
          items={[
            { key: "stock", label: "Theo ma" },
            { key: "sector", label: "Theo sector" },
            { key: "market", label: "Theo market" },
          ]}
          style={{ marginBottom: 12 }}
        />
        <Space wrap size="middle">
          <Tabs
            activeKey={windowType}
            onChange={(value) => setWindowType(value as WindowType)}
            items={[
              { key: "slot", label: "Intraday slot" },
              { key: "eod", label: "EOD" },
            ]}
          />
          <DatePicker value={tradingDate} onChange={(value) => setTradingDate(value ?? dayjs())} format="DD/MM/YYYY" />
          {windowType === "slot" ? (
            <Select<string>
              placeholder="Chon snapshot slot"
              value={snapshotSlot}
              onChange={(value) => setSnapshotSlot(value)}
              options={slotOptions.map((item) => ({ label: item, value: item }))}
              style={{ width: 170 }}
            />
          ) : null}
          {entityType === "stock" ? (
            <Input
              value={tickerFilter}
              placeholder="Loc theo ticker"
              onChange={(event) => setTickerFilter(event.target.value.toUpperCase())}
              maxLength={12}
              style={{ width: 180 }}
            />
          ) : null}
          {entityType === "sector" ? (
            <Select<number>
              allowClear
              showSearch
              value={sectorFilter}
              placeholder="Chon nhom nganh"
              onChange={(value) => setSectorFilter(value)}
              options={industries.map((item) => ({ label: `${item.name} (#${item.id})`, value: item.id }))}
              style={{ width: 260 }}
              optionFilterProp="label"
            />
          ) : null}
          <Button type="primary" onClick={() => void load(1, pagination.pageSize)} loading={loading}>
            Loc du lieu
          </Button>
          <Button onClick={resetFilters}>
            Reset
          </Button>
          <Button onClick={() => void load(pagination.current, pagination.pageSize)} loading={loading}>
            Lam moi
          </Button>
          <Button onClick={() => void rebuildFeatures()} loading={rebuilding}>
            Rebuild
          </Button>
        </Space>
        <Space wrap size="middle" style={{ marginTop: 12 }}>
          <Segmented<QuickFilter>
            value={quickFilter}
            onChange={(value) => setQuickFilter(value)}
            options={[
              { label: "Tat ca", value: "all" },
              { label: "Duong", value: "positive" },
              { label: "Am", value: "negative" },
              { label: "Low conf", value: "low_confidence" },
            ]}
          />
          <DatePicker.RangePicker
            value={backfillRange}
            onChange={(value) => setBackfillRange(value as [Dayjs | null, Dayjs | null] | null)}
            format="DD/MM/YYYY"
            allowEmpty={[true, true]}
          />
          <Button onClick={() => void backfillSlotHistory()} loading={backfillingSlot}>
            Backfill intraday lich su
          </Button>
          <Button onClick={() => void backfillEodHistory()} loading={backfillingEod}>
            Backfill EOD lich su
          </Button>
          <Typography.Text type="secondary">
            De trong khoang ngay neu muon backfill toan bo cac ngay dang co T0 snapshot.
          </Typography.Text>
        </Space>
      </Card>

      <Space wrap style={{ width: "100%" }}>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Tong entity" value={pagination.total} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Tong net flow" value={formatNumber(summary.totalNetFlow)} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="So entity duong" value={summary.positive} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="So entity am" value={summary.negative} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Low confidence" value={summary.lowConfidence} />
        </Card>
      </Space>

      <Card
        title={entityType === "stock" ? "Heatmap ma dan dau" : entityType === "sector" ? "Heatmap sector dan dau" : "Heatmap market"}
        extra={<Typography.Text type="secondary">{windowType === "slot" ? `Slot ${snapshotSlot ?? "-"}` : "EOD"}</Typography.Text>}
      >
        {!sortedRows.length && rows.length ? (
          <Alert
            style={{ marginBottom: 16 }}
            type="info"
            showIcon
            message="Bo loc nhanh dang loai het du lieu hien tai. Heatmap dang fallback sang tap du lieu goc."
          />
        ) : null}
        {heatmapRows.length ? (
          <Space wrap size="middle">
            {heatmapRows.map((row) => {
              const metric = entityType === "market" ? getNetFlowRatioValue(row) : getVsMarketStrengthValue(row) ?? getNetFlowRatioValue(row);
              return (
                <Card
                  key={row.id}
                  size="small"
                  hoverable
                  style={{
                    width: 210,
                    borderColor: ratioColor(metric) === "green" ? "#86efac" : ratioColor(metric) === "red" ? "#fca5a5" : undefined,
                    background:
                      ratioColor(metric) === "green"
                        ? "linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%)"
                        : ratioColor(metric) === "red"
                          ? "linear-gradient(180deg, #fef2f2 0%, #ffffff 100%)"
                          : ratioColor(metric) === "cyan"
                            ? "linear-gradient(180deg, #ecfeff 0%, #ffffff 100%)"
                            : undefined,
                  }}
                  onClick={() => {
                    setSelectedRow(row);
                    setDrawerOpen(true);
                  }}
                >
                  <Space direction="vertical" size={4} style={{ width: "100%" }}>
                    <Typography.Text strong>{formatEntityLabel(row, industriesById)}</Typography.Text>
                    <Typography.Text type={netFlowTextType(getNetFlowValue(row))}>
                      Net flow: {formatNumber(getNetFlowValue(row))}
                    </Typography.Text>
                    <div>{renderMetricTag(metric)}</div>
                    {row.entityType === "stock" ? <div>{renderMetricTag(getVsSectorStrengthValue(row))}</div> : null}
                  </Space>
                </Card>
              );
            })}
          </Space>
        ) : (
          <Empty description="Khong co du lieu heatmap cho bo loc hien tai" />
        )}
      </Card>

      {windowType === "slot" && !snapshotSlot ? (
        <Alert type="info" showIcon message="Intraday can chon snapshot slot de so sanh dung same-slot baseline." />
      ) : null}
      {error ? <Alert type="error" showIcon message={error} /> : null}
      {!sortedRows.length && rows.length ? (
        <Alert
          type="info"
          showIcon
          message="Bo loc nhanh dang loai het du lieu hien tai. Bang du lieu dang fallback sang tap du lieu goc."
        />
      ) : null}

      <Card title="Bang money flow features">
        {displayRows.length ? (
          <Table<MoneyFlowFeatureRow>
            rowKey="id"
            loading={loading}
            dataSource={displayRows}
            columns={columns}
            scroll={{ x: 1500 }}
            onRow={(row) => ({
              onClick: () => {
                setSelectedRow(row);
                setDrawerOpen(true);
              },
              style: { cursor: "pointer" },
            })}
            pagination={{
              current: pagination.current,
              pageSize: pagination.pageSize,
              total: pagination.total,
              showSizeChanger: true,
              onChange: (page, pageSize) => void load(page, pageSize),
            }}
          />
        ) : (
          <Empty description="Khong co money flow features cho bo loc hien tai" />
        )}
      </Card>

      <Drawer
        title={selectedRow ? `Chi tiet money flow - ${formatEntityLabel(selectedRow, industriesById)}` : "Chi tiet money flow"}
        width={760}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {selectedRow ? (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Descriptions
              size="small"
              column={2}
              items={drawerDescriptions}
            />
            <Card size="small" title="Feature payload">
              <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                {JSON.stringify(selectedRow.features, null, 2)}
              </pre>
            </Card>
          </Space>
        ) : null}
      </Drawer>
    </Space>
  );
}
