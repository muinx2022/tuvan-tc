import { SyncOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Input, Modal, Select, Space, Table, Typography, message } from "antd";
import { useEffect, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type StockSymbol = {
  id: number;
  ticker: string;
  organCode: string;
  organName: string;
  organShortName: string;
  icbCode: string;
  industryGroupId: number | null;
  industryGroupName: string | null;
  listingDate: string;
  updatedAt: string;
  historyCount: number;
};

type StockPage = {
  items: StockSymbol[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

type StockHistoryItem = {
  id: number;
  ticker: string;
  tradingDate: string;
  openPrice: number | null;
  highPrice: number | null;
  lowPrice: number | null;
  closePrice: number | null;
  volume: number | null;
  avgPrice: number | null;
  priceChanged: number | null;
  perPriceChange: number | null;
  totalMatchVol: number | null;
  totalMatchVal: number | null;
  foreignBuyVolTotal: number | null;
  foreignSellVolTotal: number | null;
};

type StockHistoryPage = {
  items: StockHistoryItem[];
  page: number;
  size: number;
  totalElements: number;
  totalPages: number;
};

type IndustryGroup = {
  id: number;
  name: string;
};

export function StocksPage() {
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [data, setData] = useState<StockPage>({
    items: [],
    page: 0,
    size: 20,
    totalElements: 0,
    totalPages: 0,
  });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [activeTicker, setActiveTicker] = useState<string>("");
  const [history, setHistory] = useState<StockHistoryPage>({
    items: [],
    page: 0,
    size: 20,
    totalElements: 0,
    totalPages: 0,
  });
  const [industryGroups, setIndustryGroups] = useState<IndustryGroup[]>([]);
  const [tickerFilter, setTickerFilter] = useState("");
  const [industryGroupFilter, setIndustryGroupFilter] = useState<number | undefined>(undefined);
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);
  const [resyncingTicker, setResyncingTicker] = useState<string | null>(null);

  async function load(
    page = data.page,
    size = data.size,
    ticker = tickerFilter,
    industryGroupId = industryGroupFilter,
  ) {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await apiClient.get<ApiEnvelope<StockPage>>("/admin/stocks", {
        params: {
          page,
          size,
          ticker: ticker.trim() || undefined,
          industryGroupId,
        },
      });
      setData(res.data.data);
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Khong tai duoc du lieu stocks";
      setLoadError(apiMessage);
      message.error(apiMessage);
    } finally {
      setLoading(false);
    }
  }

  async function loadIndustryGroups() {
    try {
      const res = await apiClient.get<ApiEnvelope<IndustryGroup[]>>("/admin/stocks/industry-groups");
      setIndustryGroups(res.data.data);
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Khong tai duoc nhom nganh";
      message.error(apiMessage);
    }
  }

  function applyFilters() {
    void load(0, data.size, tickerFilter, industryGroupFilter);
  }

  function resetFilters() {
    setTickerFilter("");
    setIndustryGroupFilter(undefined);
    void load(0, data.size, "", undefined);
  }

  async function loadHistory(ticker: string, page = 0, size = history.size) {
    setHistoryLoading(true);
    try {
      const res = await apiClient.get<ApiEnvelope<StockHistoryPage>>(`/admin/stocks/${ticker}/history`, {
        params: { page, size },
      });
      setHistory(res.data.data);
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        `Khong tai duoc lich su cho ${ticker}`;
      message.error(apiMessage);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function openHistoryModal(ticker: string) {
    if (resyncingTicker) {
      return;
    }
    setActiveTicker(ticker);
    setHistoryOpen(true);
    await loadHistory(ticker, 0, 20);
  }

  async function resyncTickerHistory(ticker: string) {
    if (resyncingTicker) {
      return;
    }
    setResyncingTicker(ticker);
    try {
      await apiClient.post<ApiEnvelope<{ ticker: string; recordsUpdated: number }>>(`/admin/stocks/${ticker}/history/resync`);
      message.success(`Da resync du lieu lich su cho ${ticker}`);
      await load(data.page, data.size, tickerFilter, industryGroupFilter);
      if (historyOpen && activeTicker === ticker) {
        await loadHistory(ticker, history.page, history.size);
      }
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        `Khong the resync du lieu cho ${ticker}`;
      message.error(apiMessage);
    } finally {
      setResyncingTicker(null);
    }
  }

  useEffect(() => {
    void load(0, 20, "", undefined);
    void loadIndustryGroups();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3}>Quan ly ma chung khoan</Typography.Title>
      <Card>
        <Space wrap style={{ marginBottom: 12 }}>
          <Input
            placeholder="Loc theo ticker"
            value={tickerFilter}
            onChange={(event) => setTickerFilter(event.target.value)}
            onPressEnter={applyFilters}
            style={{ width: 220 }}
          />
          <Select<number>
            allowClear
            placeholder="Loc theo nhom nganh"
            value={industryGroupFilter}
            onChange={(value) => setIndustryGroupFilter(value)}
            options={industryGroups.map((item) => ({ value: item.id, label: `${item.name} (#${item.id})` }))}
            style={{ width: 320 }}
          />
          <Button type="primary" onClick={applyFilters}>
            Tim
          </Button>
          <Button onClick={resetFilters}>Bo loc</Button>
        </Space>
        <Space>
          <Button onClick={() => void load()} loading={loading}>
            Refresh
          </Button>
        </Space>
        {loadError ? (
          <Alert
            style={{ marginTop: 12 }}
            type="error"
            showIcon
            message={loadError}
          />
        ) : null}
      </Card>
      <Table<StockSymbol>
        rowKey="id"
        loading={loading}
        dataSource={data.items}
        onRow={(record) => ({
          onMouseEnter: () => setHoveredTicker(record.ticker),
          onMouseLeave: () => setHoveredTicker((current) => (current === record.ticker ? null : current)),
        })}
        columns={[
          { title: "Ticker", dataIndex: "ticker" },
          { title: "Ten cong ty", dataIndex: "organName" },
          { title: "Ten viet tat", dataIndex: "organShortName" },
          {
            title: "Nganh",
            render: (_, record: StockSymbol) =>
              record.industryGroupName
                ? `${record.industryGroupName}${record.industryGroupId ? ` (#${record.industryGroupId})` : ""}`
                : "-",
          },
          {
            title: "Data",
            dataIndex: "historyCount",
            width: 120,
            render: (value: number, record: StockSymbol) => (
              <Space size="small" style={{ minWidth: 96, justifyContent: "space-between" }}>
                <Button type="link" onClick={() => void openHistoryModal(record.ticker)}>
                  {value}
                </Button>
                <span style={{ width: 24, display: "inline-flex", justifyContent: "center" }}>
                  {hoveredTicker === record.ticker ? (
                  <Button
                    type="text"
                    size="small"
                    icon={<SyncOutlined />}
                    onClick={(event) => {
                      event.stopPropagation();
                      void resyncTickerHistory(record.ticker);
                    }}
                    aria-label={`Resync ${record.ticker}`}
                    disabled={Boolean(resyncingTicker)}
                  />
                  ) : null}
                </span>
              </Space>
            ),
          },
          { title: "Ngay niem yet", dataIndex: "listingDate" },
          {
            title: "Cap nhat luc",
            dataIndex: "updatedAt",
            render: (value: string) => new Date(value).toLocaleString(),
          },
        ]}
        pagination={{
          current: data.page + 1,
          pageSize: data.size,
            total: data.totalElements,
            showSizeChanger: true,
            onChange: (page, pageSize) => {
              if (resyncingTicker) {
                return;
              }
              void load(page - 1, pageSize, tickerFilter, industryGroupFilter);
            },
          }}
      />
      <Modal
        title={`Lich su gia - ${activeTicker}`}
        open={historyOpen}
        onCancel={() => setHistoryOpen(false)}
        footer={null}
        width={1200}
      >
        <Table<StockHistoryItem>
          rowKey="id"
          loading={historyLoading}
          dataSource={history.items}
          size="small"
          columns={[
            { title: "Ngay", dataIndex: "tradingDate" },
            { title: "Open", dataIndex: "openPrice" },
            { title: "High", dataIndex: "highPrice" },
            { title: "Low", dataIndex: "lowPrice" },
            { title: "Close", dataIndex: "closePrice" },
            { title: "Volume", dataIndex: "volume" },
            { title: "Avg", dataIndex: "avgPrice" },
            { title: "Change", dataIndex: "priceChanged" },
            { title: "%", dataIndex: "perPriceChange" },
          ]}
          pagination={{
            current: history.page + 1,
            pageSize: history.size,
            total: history.totalElements,
            showSizeChanger: true,
            onChange: (page, pageSize) => {
              if (resyncingTicker) {
                return;
              }
              if (activeTicker) {
                void loadHistory(activeTicker, page - 1, pageSize);
              }
            },
          }}
        />
      </Modal>
      <Modal open={Boolean(resyncingTicker)} footer={null} closable={false} keyboard={false} maskClosable={false} centered>
        <Space direction="vertical" style={{ width: "100%", textAlign: "center" }} size="large">
          <Typography.Title level={4} style={{ marginBottom: 0 }}>
            Dang resync du lieu lich su
          </Typography.Title>
          <Typography.Text>
            Dang dong bo lai khoang 200 phien gan nhat cho <strong>{resyncingTicker}</strong> tu SSI. Vui long cho den
            khi hoan tat.
          </Typography.Text>
          <SyncOutlined spin style={{ fontSize: 28 }} />
        </Space>
      </Modal>
    </Space>
  );
}
