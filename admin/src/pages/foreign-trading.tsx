import { ArrowDownOutlined, ArrowUpOutlined } from "@ant-design/icons";
import { Alert, Button, Card, DatePicker, Descriptions, Drawer, Select, Space, Statistic, Table, Tag, Typography, message } from "antd";
import type { ColumnsType } from "antd/es/table";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiClient, type ApiEnvelope } from "../lib/api";

type IndustryGroup = {
  id: number;
  name: string;
};

type ForeignTradingRow = {
  ticker: string;
  tradingDate: string;
  organName: string | null;
  industryGroupId: number | null;
  industryGroupName: string | null;
  foreignBuyVolTotal: number;
  foreignSellVolTotal: number;
  foreignNetVolTotal: number;
  foreignEstimatedPrice: number | string | null;
  foreignBuyValEstimated: number | string | null;
  foreignSellValEstimated: number | string | null;
  foreignNetValEstimated: number | string | null;
  foreignValueSource?: string | null;
  hasForeignVolumeData?: boolean;
};

type ForeignTradingSummary = {
  tradingDate: string | null;
  totalBuyVol: number;
  totalSellVol: number;
  totalNetVol: number;
  totalBuyValEstimated: number | string | null;
  totalSellValEstimated: number | string | null;
  totalNetValEstimated: number | string | null;
  positiveCount: number;
  negativeCount: number;
  zeroCount: number;
  payloadCount?: number;
  payloadZeroCount?: number;
  estimatedCount?: number;
  missingCount?: number;
};

type ForeignTradingPage = {
  items: ForeignTradingRow[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
  summary: ForeignTradingSummary;
};

type ForeignTradingTimeline = {
  ticker: string;
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
  items: ForeignTradingRow[];
};

type StockTickerOption = {
  value: string;
  label: string;
};

type StockTickerPage = {
  items: Array<{
    ticker: string;
    organName: string | null;
  }>;
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

function isValidThreeCharTicker(value: string | null | undefined) {
  const ticker = (value ?? "").trim().toUpperCase();
  return ticker.length === 3 && /^[A-Z]+$/.test(ticker);
}

function formatNumber(value: number | string | null | undefined, fractionDigits = 2) {
  const num = typeof value === "string" ? Number(value) : value;
  if (num == null || !Number.isFinite(num)) {
    return "-";
  }
  return Intl.NumberFormat("vi-VN", { maximumFractionDigits: fractionDigits }).format(num);
}

function renderNetTag(value: number) {
  if (value > 0) {
    return <Tag color="green">Mua rong</Tag>;
  }
  if (value < 0) {
    return <Tag color="red">Ban rong</Tag>;
  }
  return <Tag>Can bang</Tag>;
}

function usesEstimatedValues(items: ForeignTradingRow[]) {
  return items.some((item) => item.foreignValueSource === "estimated");
}

function renderValueSourceTag(value: string | null | undefined) {
  if (value === "payload") {
    return <Tag color="green">Payload</Tag>;
  }
  if (value === "payload_zero") {
    return <Tag color="gold">0 tu source</Tag>;
  }
  if (value === "estimated") {
    return <Tag color="orange">Fallback</Tag>;
  }
  return <Tag>Khong co du lieu</Tag>;
}

const DEFAULT_PAGE_SIZE = 20;
const INDUSTRY_PAGE_SIZE = 200;

export function ForeignTradingPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialPage = Math.max(0, Number(searchParams.get("page") ?? 0));
  const initialSize = Math.max(1, Number(searchParams.get("size") ?? DEFAULT_PAGE_SIZE));
  const initialTicker = searchParams.get("ticker")?.trim().toUpperCase() ?? "";
  const initialIndustryGroupId = searchParams.get("industryGroupId")
    ? Number(searchParams.get("industryGroupId"))
    : undefined;
  const initialTradingDate = searchParams.get("tradingDate") ?? dayjs().format("YYYY-MM-DD");
  const [loading, setLoading] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [industryGroups, setIndustryGroups] = useState<IndustryGroup[]>([]);
  const [tickerOptions, setTickerOptions] = useState<StockTickerOption[]>([]);
  const [tickerOptionsLoading, setTickerOptionsLoading] = useState(false);
  const [tickerFilter, setTickerFilter] = useState(initialTicker);
  const [industryGroupFilter, setIndustryGroupFilter] = useState<number | undefined>(initialIndustryGroupId);
  const [dateFilter, setDateFilter] = useState(dayjs(initialTradingDate));
  const [data, setData] = useState<ForeignTradingPage>({
    items: [],
    page: initialPage,
    size: initialSize,
    totalElements: 0,
    totalPages: 0,
    summary: {
      tradingDate: null,
      totalBuyVol: 0,
      totalSellVol: 0,
      totalNetVol: 0,
      totalBuyValEstimated: 0,
      totalSellValEstimated: 0,
      totalNetValEstimated: 0,
      positiveCount: 0,
      negativeCount: 0,
      zeroCount: 0,
    },
  });
  const [timelineOpen, setTimelineOpen] = useState(false);
  const [timeline, setTimeline] = useState<ForeignTradingTimeline | null>(null);
  const hasEstimatedRows = useMemo(() => usesEstimatedValues(data.items), [data.items]);

  function updateSearch(next: { page: number; size: number; ticker?: string; industryGroupId?: number; tradingDate?: string }) {
    setSearchParams((prev) => {
      const params = new URLSearchParams(prev);
      params.set("page", String(next.page));
      params.set("size", String(next.size));
      if ((next.ticker ?? "").trim()) {
        params.set("ticker", (next.ticker ?? "").trim().toUpperCase());
      } else {
        params.delete("ticker");
      }
      if (next.industryGroupId != null) {
        params.set("industryGroupId", String(next.industryGroupId));
      } else {
        params.delete("industryGroupId");
      }
      if (next.tradingDate) {
        params.set("tradingDate", next.tradingDate);
      } else {
        params.delete("tradingDate");
      }
      return params;
    }, { replace: true });
  }

  function resolvePageSize(industryGroupId?: number, explicitSize?: number) {
    if (explicitSize != null) {
      return explicitSize;
    }
    return industryGroupId ? INDUSTRY_PAGE_SIZE : DEFAULT_PAGE_SIZE;
  }

  async function loadIndustryGroups() {
    try {
      const res = await apiClient.get<ApiEnvelope<IndustryGroup[]>>("/admin/stocks/industry-groups");
      setIndustryGroups(res.data.data);
    } catch {
      message.error("Khong tai duoc nhom nganh");
    }
  }

  async function loadTickerOptions(industryGroupId?: number) {
    if (!industryGroupId) {
      setTickerOptions([]);
      return;
    }
    setTickerOptionsLoading(true);
    try {
      const pageSize = 200;
      const collected: StockTickerOption[] = [];
      let page = 0;
      let totalPages = 1;
      while (page < totalPages) {
        const res = await apiClient.get<ApiEnvelope<StockTickerPage>>("/admin/stocks", {
          params: {
            page,
            size: pageSize,
            industryGroupId,
          },
        });
        const payload = res.data.data;
        collected.push(
          ...payload.items
            .filter((item) => isValidThreeCharTicker(item.ticker))
            .map((item) => ({
              value: item.ticker.trim().toUpperCase(),
              label: item.organName ? `${item.ticker.trim().toUpperCase()} - ${item.organName}` : item.ticker.trim().toUpperCase(),
            })),
        );
        totalPages = payload.totalPages;
        page += 1;
      }
      setTickerOptions(collected.sort((left, right) => left.value.localeCompare(right.value)));
    } catch {
      setTickerOptions([]);
      message.error("Khong tai duoc danh sach ticker theo nhom nganh");
    } finally {
      setTickerOptionsLoading(false);
    }
  }

  function resetFilters() {
    setTickerFilter("");
    setIndustryGroupFilter(undefined);
    setTickerOptions([]);
    const today = dayjs();
    setDateFilter(today);
    const nextSize = DEFAULT_PAGE_SIZE;
    setSearchParams({}, { replace: true });
    void load(0, nextSize, { ticker: undefined, industryGroupId: undefined, tradingDate: today.format("YYYY-MM-DD") });
  }

  async function load(
    page = data.page,
    size = data.size,
    nextFilters?: { ticker?: string; industryGroupId?: number; tradingDate?: string },
  ) {
    setLoading(true);
    setError(null);
    try {
      const resolvedTicker = nextFilters?.ticker !== undefined ? nextFilters.ticker : (tickerFilter.trim().toUpperCase() || undefined);
      const resolvedIndustryGroupId = nextFilters?.industryGroupId ?? industryGroupFilter;
      const resolvedTradingDate = nextFilters?.tradingDate ?? dateFilter.format("YYYY-MM-DD");
      const resolvedSize = resolvePageSize(resolvedIndustryGroupId, size);
      updateSearch({
        page,
        size: resolvedSize,
        ticker: resolvedTicker,
        industryGroupId: resolvedIndustryGroupId,
        tradingDate: resolvedTradingDate,
      });
      const res = await apiClient.get<ApiEnvelope<ForeignTradingPage>>("/admin/stocks/foreign-trading", {
        params: {
          page,
          size: resolvedSize,
          ticker: resolvedTicker,
          industryGroupId: resolvedIndustryGroupId,
          tradingDate: resolvedTradingDate,
        },
      });
      setData(res.data.data);
    } catch (caught) {
      console.error(caught);
      setError("Khong tai duoc du lieu giao dich nuoc ngoai.");
    } finally {
      setLoading(false);
    }
  }

  async function openTimeline(row: ForeignTradingRow) {
    setTimelineOpen(true);
    setTimelineLoading(true);
    try {
      const res = await apiClient.get<ApiEnvelope<ForeignTradingTimeline>>(`/admin/stocks/foreign-trading/${row.ticker}`, {
        params: { page: 0, size: 60 },
      });
      setTimeline(res.data.data);
    } catch {
      message.error(`Khong tai duoc lich su nuoc ngoai cho ${row.ticker}`);
    } finally {
      setTimelineLoading(false);
    }
  }

  useEffect(() => {
    void loadIndustryGroups();
    if (initialIndustryGroupId) {
      void loadTickerOptions(initialIndustryGroupId);
    }
    void load(initialPage, resolvePageSize(initialIndustryGroupId, initialSize), {
      ticker: initialTicker || undefined,
      industryGroupId: initialIndustryGroupId,
      tradingDate: initialTradingDate,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const columns: ColumnsType<ForeignTradingRow> = useMemo(
    () => [
      { title: "Ticker", dataIndex: "ticker", width: 90, render: (value) => <Typography.Text strong>{value}</Typography.Text> },
      { title: "Ten cong ty", dataIndex: "organName", width: 220, render: (value) => value || "-" },
      { title: "Nganh", dataIndex: "industryGroupName", width: 160, render: (value) => value || "-" },
      { title: "Mua vol", dataIndex: "foreignBuyVolTotal", align: "right", width: 120, render: (value) => formatNumber(value, 0) },
      { title: "Ban vol", dataIndex: "foreignSellVolTotal", align: "right", width: 120, render: (value) => formatNumber(value, 0) },
      { title: "Net vol", dataIndex: "foreignNetVolTotal", align: "right", width: 120, render: (value: number) => <Typography.Text type={value > 0 ? "success" : value < 0 ? "danger" : undefined}>{formatNumber(value, 0)}</Typography.Text> },
      { title: "Mua gia tri", dataIndex: "foreignBuyValEstimated", align: "right", width: 130, render: (value) => formatNumber(value) },
      { title: "Ban gia tri", dataIndex: "foreignSellValEstimated", align: "right", width: 130, render: (value) => formatNumber(value) },
      { title: "Net gia tri", dataIndex: "foreignNetValEstimated", align: "right", width: 130, render: (value: number | string | null) => {
        const num = typeof value === "string" ? Number(value) : value ?? 0;
        return <Typography.Text type={num > 0 ? "success" : num < 0 ? "danger" : undefined}>{formatNumber(num)}</Typography.Text>;
      } },
      { title: "Nguon", dataIndex: "foreignValueSource", width: 120, render: (value: string | null | undefined) => renderValueSourceTag(value) },
      { title: "Trang thai", dataIndex: "foreignNetVolTotal", width: 110, render: (value: number) => renderNetTag(value) },
    ],
    [],
  );

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <div>
        <Typography.Title level={3} style={{ marginBottom: 0 }}>
          Giao dich nuoc ngoai
        </Typography.Title>
        <Typography.Text type="secondary">
          Theo doi mua, ban va net theo khoi ngoai. Uu tien dung gia tri thuc tu payload SSI, chi fallback sang avg price khi payload thieu field value.
        </Typography.Text>
      </div>

      <Card>
        <Space wrap>
          <DatePicker value={dateFilter} onChange={(value) => setDateFilter(value ?? dayjs())} format="DD/MM/YYYY" />
          <Select<string>
            allowClear
            showSearch
            value={tickerFilter}
            placeholder={industryGroupFilter ? "Chon hoac go ticker trong nhom" : "Loc theo ma CK"}
            onChange={(value) => setTickerFilter((value ?? "").toUpperCase())}
            onSearch={(value) => setTickerFilter((value ?? "").toUpperCase())}
            options={tickerOptions}
            filterOption={(inputValue, option) =>
              String(option?.value ?? "").toUpperCase().includes(inputValue.toUpperCase()) ||
              String(option?.label ?? "").toUpperCase().includes(inputValue.toUpperCase())
            }
            optionFilterProp="label"
            style={{ width: 260 }}
            notFoundContent={industryGroupFilter ? (tickerOptionsLoading ? "Dang tai ticker..." : "Khong co ticker") : "Chon nhom nganh de tai ticker"}
          />
          <Select<number>
            allowClear
            placeholder="Loc theo nhom nganh"
            value={industryGroupFilter}
            onChange={(value) => {
              setIndustryGroupFilter(value);
              setTickerFilter("");
              void loadTickerOptions(value);
            }}
            options={industryGroups.map((item) => ({ value: item.id, label: item.name }))}
            style={{ width: 260 }}
            loading={tickerOptionsLoading}
          />
          <Button type="primary" onClick={() => void load(0, resolvePageSize(industryGroupFilter), {
            ticker: tickerFilter.trim().toUpperCase() || undefined,
            industryGroupId: industryGroupFilter,
            tradingDate: dateFilter.format("YYYY-MM-DD"),
          })} loading={loading}>
            Loc du lieu
          </Button>
          <Button onClick={resetFilters}>
            Reset
          </Button>
          <Button
            onClick={() => {
              setTickerFilter("");
              setIndustryGroupFilter(undefined);
              setTickerOptions([]);
              const today = dayjs();
              setDateFilter(today);
              void load(0, DEFAULT_PAGE_SIZE, { ticker: undefined, industryGroupId: undefined, tradingDate: today.format("YYYY-MM-DD") });
            }}
          >
            Hom nay
          </Button>
        </Space>
      </Card>

      <Space wrap style={{ width: "100%" }}>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Mua gia tri" value={formatNumber(data.summary.totalBuyValEstimated)} prefix={<ArrowUpOutlined />} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Ban gia tri" value={formatNumber(data.summary.totalSellValEstimated)} prefix={<ArrowDownOutlined />} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Net gia tri" value={formatNumber(data.summary.totalNetValEstimated)} valueStyle={{ color: Number(data.summary.totalNetValEstimated ?? 0) >= 0 ? "#15803d" : "#b91c1c" }} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="So ma mua rong" value={data.summary.positiveCount} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="So ma ban rong" value={data.summary.negativeCount} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="0 tu source" value={data.summary.payloadZeroCount ?? 0} />
        </Card>
        <Card style={{ minWidth: 220 }}>
          <Statistic title="Khong co du lieu" value={data.summary.missingCount ?? 0} />
        </Card>
      </Space>

      {error ? <Alert type="error" showIcon message={error} /> : null}
      {hasEstimatedRows ? <Alert type="warning" showIcon message="Mot so dong dang fallback sang avg price vi payload SSI khong co gia tri mua/ban ngoai." /> : null}
      {(data.summary.payloadZeroCount ?? 0) > 0 ? <Alert type="info" showIcon message={`Ngay ${data.summary.tradingDate ?? "-"} co ${data.summary.payloadZeroCount} ma duoc source SSI tra ve 0/0 cho giao dich nuoc ngoai.`} /> : null}
      {(data.summary.missingCount ?? 0) > 0 ? <Alert type="warning" showIcon message={`Ngay ${data.summary.tradingDate ?? "-"} co ${data.summary.missingCount} ma khong co field giao dich nuoc ngoai tu source.`} /> : null}

      <Card title={`Bang tong hop ngay ${data.summary.tradingDate ?? "-"}`}>
        <Table<ForeignTradingRow>
          rowKey={(row) => `${row.ticker}-${row.tradingDate}`}
          loading={loading}
          dataSource={data.items}
          columns={columns}
          onRow={(row) => ({
            onClick: () => void openTimeline(row),
            style: { cursor: "pointer" },
          })}
          scroll={{ x: 1400 }}
          pagination={{
            current: data.page + 1,
            pageSize: data.size,
            total: data.totalElements,
            showSizeChanger: true,
            onChange: (page, pageSize) => void load(page - 1, pageSize),
          }}
        />
      </Card>

      <Drawer
        title={timeline ? `Dong tien nuoc ngoai - ${timeline.ticker}` : "Dong tien nuoc ngoai"}
        width={960}
        open={timelineOpen}
        onClose={() => setTimelineOpen(false)}
      >
        {timelineLoading ? (
          <Typography.Text>Dang tai du lieu...</Typography.Text>
        ) : timeline ? (
          <Space direction="vertical" style={{ width: "100%" }} size="middle">
            <Descriptions size="small" column={3}>
              <Descriptions.Item label="Ticker">{timeline.ticker}</Descriptions.Item>
              <Descriptions.Item label="So phien">{timeline.totalElements}</Descriptions.Item>
              <Descriptions.Item label="Gia tri">{timeline.items.length ? (usesEstimatedValues(timeline.items) ? "Tron payload va fallback" : "Payload SSI") : "-"}</Descriptions.Item>
            </Descriptions>
            <Table<ForeignTradingRow>
              rowKey={(row) => `${row.ticker}-${row.tradingDate}`}
              size="small"
              pagination={false}
              dataSource={timeline.items}
              columns={[
                { title: "Ngay", dataIndex: "tradingDate", width: 110 },
                { title: "Mua vol", dataIndex: "foreignBuyVolTotal", align: "right", render: (value) => formatNumber(value, 0) },
                { title: "Ban vol", dataIndex: "foreignSellVolTotal", align: "right", render: (value) => formatNumber(value, 0) },
                { title: "Net vol", dataIndex: "foreignNetVolTotal", align: "right", render: (value: number) => formatNumber(value, 0) },
                { title: "Mua gia tri", dataIndex: "foreignBuyValEstimated", align: "right", render: (value) => formatNumber(value) },
                { title: "Ban gia tri", dataIndex: "foreignSellValEstimated", align: "right", render: (value) => formatNumber(value) },
                { title: "Net gia tri", dataIndex: "foreignNetValEstimated", align: "right", render: (value) => formatNumber(value) },
                { title: "Nguon", dataIndex: "foreignValueSource", render: (value: string | null | undefined) => renderValueSourceTag(value) },
                { title: "Trang thai", dataIndex: "foreignNetVolTotal", render: (value: number) => renderNetTag(value) },
              ]}
            />
          </Space>
        ) : (
          <Typography.Text type="secondary">Khong co du lieu.</Typography.Text>
        )}
      </Drawer>
    </Space>
  );
}
