import { MinusCircleOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Col, Descriptions, Form, Input, InputNumber, Row, Select, Space, Tabs, Typography } from "antd";
import { useEffect, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";
import type { MediaSetting, MediaSettingFormValues } from "../lib/media";

type DnseSetting = {
  id: number;
  apiKey: string | null;
  apiSecret: string | null;
  updatedAt: string;
};

type DnseFormValues = {
  apiKey?: string;
  apiSecret?: string;
};

type SsiFcSetting = {
  consumerId: string | null;
  consumerSecret: string | null;
};

type SsiFcFormValues = {
  consumerId?: string;
  consumerSecret?: string;
};

type GoogleOauthSetting = {
  enabled: boolean;
  clientId: string | null;
  clientSecret: string | null;
};

type GoogleOauthFormValues = {
  enabled?: boolean;
  clientId?: string;
  clientSecret?: string;
};

type HistorySyncScheduleSetting = {
  enabled: boolean;
  hour: number;
  minute: number;
  runtime: {
    lastAttemptedDate: string | null;
    lastStartedAt: string | null;
    lastError: string | null;
  };
};

type HistorySyncScheduleFormValues = {
  enabled?: boolean;
  hour?: number;
  minute?: number;
};

type T0SnapshotScheduleSetting = {
  enabled: boolean;
  times: string[];
  foreignRefreshMinutes: number;
  foreignStartTime: string;
  foreignEndTime: string;
  projectionSlots: string[];
  projectionWindow20: number;
  projectionWindow5: number;
  projectionWeight20: number;
  projectionWeight5: number;
  projectionFinalSlot: string;
  timezone: string;
};

type T0SnapshotScheduleFormValues = {
  enabled?: boolean;
  times?: string[];
  foreignRefreshMinutes?: number;
  foreignStartTime?: string;
  foreignEndTime?: string;
  projectionSlots?: string[];
  projectionWindow20?: number;
  projectionWindow5?: number;
  projectionWeight20?: number;
  projectionWeight5?: number;
  projectionFinalSlot?: string;
};

type MoneyFlowFeatureSetting = {
  historyBaselineDays: number;
  historyMinDaysForStable: number;
  historyAllowPartialBaseline: boolean;
  intradaySlotMode: "strict_same_slot";
  lowHistoryConfidenceMode: "flag_only";
};

type MoneyFlowFeatureFormValues = {
  historyBaselineDays?: number;
  historyMinDaysForStable?: number;
  historyAllowPartialBaseline?: boolean;
  intradaySlotMode?: "strict_same_slot";
  lowHistoryConfidenceMode?: "flag_only";
};

const DEFAULT_T0_TIMES = [
  "09:15",
  "09:30",
  "09:45",
  "10:00",
  "10:15",
  "10:30",
  "10:45",
  "11:00",
  "11:15",
  "11:30",
  "13:00",
  "13:15",
  "13:30",
  "13:45",
  "14:00",
  "14:15",
  "14:30",
  "14:45",
  "15:00",
];

function DnseTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<DnseFormValues>>[0];
  loading: boolean;
}) {
  return (
    <Card loading={loading}>
      <Form<DnseFormValues> form={form} layout="vertical">
        <Form.Item label="API Key" name="apiKey">
          <Input placeholder="Nhap DNSE API key" />
        </Form.Item>
        <Form.Item label="API Secret" name="apiSecret">
          <Input.Password placeholder="Nhap DNSE API secret" />
        </Form.Item>
      </Form>
    </Card>
  );
}

function SsiFcTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<SsiFcFormValues>>[0];
  loading: boolean;
}) {
  return (
    <Card loading={loading}>
      <Typography.Paragraph type="secondary">
        Cau hinh nay dung cho SSI FC API de lay giao dich nuoc ngoai intraday vao luc chup snapshot T0.
      </Typography.Paragraph>
      <Form<SsiFcFormValues> form={form} layout="vertical">
        <Form.Item label="Consumer ID" name="consumerId">
          <Input placeholder="Nhap SSI FC consumer ID" />
        </Form.Item>
        <Form.Item label="Consumer Secret" name="consumerSecret">
          <Input.Password placeholder="Nhap SSI FC consumer secret" />
        </Form.Item>
      </Form>
    </Card>
  );
}

function MediaTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<MediaSettingFormValues>>[0];
  loading: boolean;
}) {
  const provider = Form.useWatch("provider", form) ?? "cloudinary";

  return (
    <Card loading={loading}>
      <Form<MediaSettingFormValues> form={form} layout="vertical">
        <Form.Item label="Provider" name="provider" rules={[{ required: true, message: "Provider is required" }]}>
          <Select
            options={[
              { value: "local", label: "Local" },
              { value: "cloudinary", label: "Cloudinary" },
              { value: "cloudflare_s3", label: "Cloudflare S3" },
            ]}
          />
        </Form.Item>

        {provider === "local" ? (
          <>
            <Form.Item label="Local Root Path" name="localRootPath">
              <Input placeholder="uploads" />
            </Form.Item>
            <Form.Item label="Local Public Base URL" name="localPublicBaseUrl">
              <Input placeholder="http://localhost:8080/api/v1/public/media" />
            </Form.Item>
          </>
        ) : null}

        {provider === "cloudinary" ? (
          <>
            <Form.Item label="Cloud Name" name="cloudinaryCloudName">
              <Input />
            </Form.Item>
            <Form.Item label="API Key" name="cloudinaryApiKey">
              <Input />
            </Form.Item>
            <Form.Item label="API Secret" name="cloudinaryApiSecret">
              <Input.Password />
            </Form.Item>
            <Form.Item label="Folder" name="cloudinaryFolder">
              <Input placeholder="posts" />
            </Form.Item>
          </>
        ) : null}

        {provider === "cloudflare_s3" ? (
          <>
            <Form.Item label="Endpoint" name="cloudflareS3Endpoint">
              <Input placeholder="https://<accountid>.r2.cloudflarestorage.com" />
            </Form.Item>
            <Form.Item label="Access Key" name="cloudflareS3AccessKey">
              <Input />
            </Form.Item>
            <Form.Item label="Secret Key" name="cloudflareS3SecretKey">
              <Input.Password />
            </Form.Item>
            <Form.Item label="Bucket" name="cloudflareS3Bucket">
              <Input />
            </Form.Item>
            <Form.Item label="Region" name="cloudflareS3Region">
              <Input placeholder="auto" />
            </Form.Item>
            <Form.Item label="Public Base URL" name="cloudflareS3PublicBaseUrl">
              <Input placeholder="https://cdn.example.com" />
            </Form.Item>
          </>
        ) : null}
      </Form>
    </Card>
  );
}

function GoogleOauthTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<GoogleOauthFormValues>>[0];
  loading: boolean;
}) {
  return (
    <Card loading={loading}>
      <Form<GoogleOauthFormValues> form={form} layout="vertical">
        <Form.Item label="Trang thai" name="enabled">
          <Select
            options={[
              { value: true, label: "Bat" },
              { value: false, label: "Tat" },
            ]}
          />
        </Form.Item>
        <Form.Item label="Client ID" name="clientId">
          <Input placeholder="Nhap Google OAuth client ID" />
        </Form.Item>
        <Form.Item label="Client Secret" name="clientSecret">
          <Input.Password placeholder="Nhap Google OAuth client secret (neu can)" />
        </Form.Item>
      </Form>
    </Card>
  );
}

function HistorySyncScheduleTab({
  form,
  loading,
  runtime,
}: {
  form: ReturnType<typeof Form.useForm<HistorySyncScheduleFormValues>>[0];
  loading: boolean;
  runtime: HistorySyncScheduleSetting["runtime"] | null;
}) {
  return (
    <Card loading={loading}>
      <Typography.Paragraph type="secondary">
        Cau hinh nay se tu dong kich hoat sync du lieu lich su tu man hinh <code>/sync-data</code> theo gio ban dat.
        Mac dinh 00:00 moi ngay.
      </Typography.Paragraph>
      <Form<HistorySyncScheduleFormValues> form={form} layout="vertical">
        <Form.Item label="Trang thai" name="enabled">
          <Select
            options={[
              { value: true, label: "Bat" },
              { value: false, label: "Tat" },
            ]}
          />
        </Form.Item>
        <Space align="start" size="large" wrap>
          <Form.Item label="Gio" name="hour" rules={[{ required: true, message: "Gio la bat buoc" }]}>
            <InputNumber min={0} max={23} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item label="Phut" name="minute" rules={[{ required: true, message: "Phut la bat buoc" }]}>
            <InputNumber min={0} max={59} style={{ width: 120 }} />
          </Form.Item>
        </Space>
      </Form>
      <Descriptions size="small" column={1} style={{ marginTop: 12 }}>
        <Descriptions.Item label="Lan scheduler thu gan nhat">{runtime?.lastAttemptedDate ?? "-"}</Descriptions.Item>
        <Descriptions.Item label="Lan bat dau sync gan nhat">{runtime?.lastStartedAt ?? "-"}</Descriptions.Item>
      </Descriptions>
      {runtime?.lastError ? <Alert style={{ marginTop: 12 }} type="warning" showIcon message={runtime.lastError} /> : null}
    </Card>
  );
}

function T0SnapshotScheduleTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<T0SnapshotScheduleFormValues>>[0];
  loading: boolean;
}) {
  const scheduleTimes = Form.useWatch("times", form) ?? [];

  return (
    <Card loading={loading}>
      <Form<T0SnapshotScheduleFormValues> form={form} layout="vertical">
        <Form.Item label="Trang thai" name="enabled">
          <Select
            options={[
              { value: true, label: "Bat" },
              { value: false, label: "Tat" },
            ]}
          />
        </Form.Item>

        <Row gutter={24} align="top">
          <Col xs={24} lg={12}>
            <Card size="small" title="Lich Schedule">
              <Typography.Paragraph type="secondary">
                Worker T0 se chup snapshot luy ke theo gio VN. Dinh dang moi moc la <code>HH:mm</code>, tu dong sap xep va bo trung khi luu.
              </Typography.Paragraph>
              <Form.Item
                label="Chu ky cap nhat foreign T0"
                name="foreignRefreshMinutes"
                rules={[{ required: true, message: "Bat buoc" }]}
                extra="Moi N phut se tai lai full board HOSE/HNX/UPCOM tu SSI de cap nhat giao dich nuoc ngoai trong ngay."
              >
                <InputNumber min={1} max={240} style={{ width: "100%", maxWidth: 220 }} addonAfter="phut" />
              </Form.Item>
              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item
                    label="Bat dau foreign T0"
                    name="foreignStartTime"
                    rules={[
                      { required: true, message: "Bat buoc" },
                      { pattern: /^\d{2}:\d{2}$/, message: "Dung dinh dang HH:mm" },
                    ]}
                  >
                    <Input placeholder="09:15" />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item
                    label="Ket thuc foreign T0"
                    name="foreignEndTime"
                    rules={[
                      { required: true, message: "Bat buoc" },
                      { pattern: /^\d{2}:\d{2}$/, message: "Dung dinh dang HH:mm" },
                    ]}
                  >
                    <Input placeholder="15:00" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.List name="times">
                {(fields, { add, remove }) => (
                  <Space direction="vertical" style={{ width: "100%" }} size="middle">
                    {fields.map((field) => (
                      <Space key={field.key} align="baseline">
                        <Form.Item
                          {...field}
                          label={field.name === 0 ? "Lich ghi du lieu T0" : ""}
                          rules={[
                            { required: true, message: "Nhap gio theo HH:mm" },
                            { pattern: /^\d{2}:\d{2}$/, message: "Dung dinh dang HH:mm" },
                          ]}
                          style={{ minWidth: 180 }}
                        >
                          <Input placeholder="09:15" />
                        </Form.Item>
                        <Button icon={<MinusCircleOutlined />} onClick={() => remove(field.name)} />
                      </Space>
                    ))}
                    <Button icon={<PlusOutlined />} onClick={() => add("")} style={{ width: "fit-content" }}>
                      Them moc gio
                    </Button>
                    <Typography.Text type="secondary">Timezone co dinh: Asia/Ho_Chi_Minh</Typography.Text>
                  </Space>
                )}
              </Form.List>
            </Card>
          </Col>

          <Col xs={24} lg={12}>
            <Card size="small" title="Cau Hinh GTDK">
              <Typography.Paragraph type="secondary">
                Cau hinh GTDK tren web: chon cac moc 1 gio de tinh, so phien TB20/TB5 va trong so cua tung nhom.
              </Typography.Paragraph>
              <Button
                style={{ marginBottom: 12 }}
                onClick={() => form.setFieldsValue({ projectionSlots: scheduleTimes })}
                disabled={!scheduleTimes.length}
              >
                Copy tu lich T0
              </Button>
              <Form.List name="projectionSlots">
                {(fields, { add, remove }) => (
                  <Space direction="vertical" style={{ width: "100%" }} size="middle">
                    {fields.map((field) => (
                      <Space key={field.key} align="baseline">
                        <Form.Item
                          {...field}
                          label={field.name === 0 ? "Moc tinh GTDK" : ""}
                          rules={[
                            { required: true, message: "Nhap gio theo HH:mm" },
                            { pattern: /^\d{2}:\d{2}$/, message: "Dung dinh dang HH:mm" },
                          ]}
                          style={{ minWidth: 180 }}
                        >
                          <Input placeholder="14:00" />
                        </Form.Item>
                        <Button icon={<MinusCircleOutlined />} onClick={() => remove(field.name)} />
                      </Space>
                    ))}
                    <Button icon={<PlusOutlined />} onClick={() => add("")} style={{ width: "fit-content" }}>
                      Them moc GTDK
                    </Button>
                  </Space>
                )}
              </Form.List>

              <Row gutter={16}>
                <Col xs={24} sm={12}>
                  <Form.Item label="So phien TB dai" name="projectionWindow20" rules={[{ required: true, message: "Bat buoc" }]}>
                    <InputNumber min={1} max={250} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item label="So phien TB ngan" name="projectionWindow5" rules={[{ required: true, message: "Bat buoc" }]}>
                    <InputNumber min={1} max={250} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item label="Trong so TB dai" name="projectionWeight20" rules={[{ required: true, message: "Bat buoc" }]}>
                    <InputNumber min={0} max={1} step={0.1} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item label="Trong so TB ngan" name="projectionWeight5" rules={[{ required: true, message: "Bat buoc" }]}>
                    <InputNumber min={0} max={1} step={0.1} style={{ width: "100%" }} />
                  </Form.Item>
                </Col>
                <Col xs={24} sm={12}>
                  <Form.Item label="Moc final" name="projectionFinalSlot" rules={[{ required: true, message: "Bat buoc" }]}>
                    <Input placeholder="15:00" />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}

function MoneyFlowFeatureTab({
  form,
  loading,
}: {
  form: ReturnType<typeof Form.useForm<MoneyFlowFeatureFormValues>>[0];
  loading: boolean;
}) {
  return (
    <Card loading={loading}>
      <Typography.Paragraph type="secondary">
        Cau hinh nay dieu khien so ngay lich su dung de tinh baseline cho Money Flow Derived va Market Strength.
      </Typography.Paragraph>
      <Form<MoneyFlowFeatureFormValues> form={form} layout="vertical">
        <Row gutter={16}>
          <Col xs={24} sm={12}>
            <Form.Item label="So ngay baseline" name="historyBaselineDays" rules={[{ required: true, message: "Bat buoc" }]}>
              <InputNumber min={1} max={250} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="So ngay toi thieu on dinh" name="historyMinDaysForStable" rules={[{ required: true, message: "Bat buoc" }]}>
              <InputNumber min={1} max={250} style={{ width: "100%" }} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="Cho phep baseline partial" name="historyAllowPartialBaseline">
              <Select
                options={[
                  { value: true, label: "Co" },
                  { value: false, label: "Khong" },
                ]}
              />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="Intraday slot mode" name="intradaySlotMode" rules={[{ required: true, message: "Bat buoc" }]}>
              <Select options={[{ value: "strict_same_slot", label: "Strict same slot" }]} />
            </Form.Item>
          </Col>
          <Col xs={24} sm={12}>
            <Form.Item label="Low history confidence mode" name="lowHistoryConfidenceMode" rules={[{ required: true, message: "Bat buoc" }]}>
              <Select options={[{ value: "flag_only", label: "Flag only" }]} />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </Card>
  );
}

export function SettingsPage() {
  const [loadingDnse, setLoadingDnse] = useState(false);
  const [loadingMedia, setLoadingMedia] = useState(false);
  const [loadingSsiFc, setLoadingSsiFc] = useState(false);
  const [loadingGoogleOauth, setLoadingGoogleOauth] = useState(false);
  const [loadingHistorySchedule, setLoadingHistorySchedule] = useState(false);
  const [loadingT0Schedule, setLoadingT0Schedule] = useState(false);
  const [loadingMoneyFlowFeatures, setLoadingMoneyFlowFeatures] = useState(false);
  const [savingAll, setSavingAll] = useState(false);
  const [historyRuntime, setHistoryRuntime] = useState<HistorySyncScheduleSetting["runtime"] | null>(null);

  const [dnseForm] = Form.useForm<DnseFormValues>();
  const [ssiFcForm] = Form.useForm<SsiFcFormValues>();
  const [mediaForm] = Form.useForm<MediaSettingFormValues>();
  const [googleOauthForm] = Form.useForm<GoogleOauthFormValues>();
  const [historyScheduleForm] = Form.useForm<HistorySyncScheduleFormValues>();
  const [t0ScheduleForm] = Form.useForm<T0SnapshotScheduleFormValues>();
  const [moneyFlowFeatureForm] = Form.useForm<MoneyFlowFeatureFormValues>();

  async function loadDnse() {
    setLoadingDnse(true);
    try {
      const res = await apiClient.get<ApiEnvelope<DnseSetting>>("/admin/settings/dnse");
      dnseForm.setFieldsValue({
        apiKey: res.data.data.apiKey ?? "",
        apiSecret: res.data.data.apiSecret ?? "",
      });
    } finally {
      setLoadingDnse(false);
    }
  }

  async function loadMedia() {
    setLoadingMedia(true);
    try {
      const res = await apiClient.get<ApiEnvelope<MediaSetting>>("/admin/settings/media");
      mediaForm.setFieldsValue({
        provider: res.data.data.provider,
        localRootPath: res.data.data.localRootPath ?? "",
        localPublicBaseUrl: res.data.data.localPublicBaseUrl ?? "",
        cloudinaryCloudName: res.data.data.cloudinaryCloudName ?? "",
        cloudinaryApiKey: res.data.data.cloudinaryApiKey ?? "",
        cloudinaryApiSecret: res.data.data.cloudinaryApiSecret ?? "",
        cloudinaryFolder: res.data.data.cloudinaryFolder ?? "",
        cloudflareS3Endpoint: res.data.data.cloudflareS3Endpoint ?? "",
        cloudflareS3AccessKey: res.data.data.cloudflareS3AccessKey ?? "",
        cloudflareS3SecretKey: res.data.data.cloudflareS3SecretKey ?? "",
        cloudflareS3Bucket: res.data.data.cloudflareS3Bucket ?? "",
        cloudflareS3Region: res.data.data.cloudflareS3Region ?? "",
        cloudflareS3PublicBaseUrl: res.data.data.cloudflareS3PublicBaseUrl ?? "",
      });
    } finally {
      setLoadingMedia(false);
    }
  }

  async function loadSsiFc() {
    setLoadingSsiFc(true);
    try {
      const res = await apiClient.get<ApiEnvelope<SsiFcSetting>>("/admin/settings/ssi-fc");
      ssiFcForm.setFieldsValue({
        consumerId: res.data.data.consumerId ?? "",
        consumerSecret: res.data.data.consumerSecret ?? "",
      });
    } finally {
      setLoadingSsiFc(false);
    }
  }

  async function loadGoogleOauth() {
    setLoadingGoogleOauth(true);
    try {
      const res = await apiClient.get<ApiEnvelope<GoogleOauthSetting>>("/admin/settings/google-oauth");
      googleOauthForm.setFieldsValue({
        enabled: res.data.data.enabled,
        clientId: res.data.data.clientId ?? "",
        clientSecret: res.data.data.clientSecret ?? "",
      });
    } finally {
      setLoadingGoogleOauth(false);
    }
  }

  async function loadHistorySchedule() {
    setLoadingHistorySchedule(true);
    try {
      const res = await apiClient.get<ApiEnvelope<HistorySyncScheduleSetting>>("/admin/settings/history-sync-schedule");
      historyScheduleForm.setFieldsValue({
        enabled: res.data.data.enabled,
        hour: res.data.data.hour ?? 0,
        minute: res.data.data.minute ?? 0,
      });
      setHistoryRuntime(res.data.data.runtime ?? null);
    } finally {
      setLoadingHistorySchedule(false);
    }
  }

  async function loadT0Schedule() {
    setLoadingT0Schedule(true);
    try {
      const res = await apiClient.get<ApiEnvelope<T0SnapshotScheduleSetting>>("/admin/settings/t0-snapshot-schedule");
      t0ScheduleForm.setFieldsValue({
        enabled: res.data.data.enabled,
        times: res.data.data.times.length ? res.data.data.times : DEFAULT_T0_TIMES,
        projectionSlots: res.data.data.projectionSlots.length ? res.data.data.projectionSlots : DEFAULT_T0_TIMES,
        foreignRefreshMinutes: res.data.data.foreignRefreshMinutes ?? 15,
        foreignStartTime: res.data.data.foreignStartTime ?? "09:15",
        foreignEndTime: res.data.data.foreignEndTime ?? "15:00",
        projectionWindow20: res.data.data.projectionWindow20 ?? 20,
        projectionWindow5: res.data.data.projectionWindow5 ?? 5,
        projectionWeight20: res.data.data.projectionWeight20 ?? 0.6,
        projectionWeight5: res.data.data.projectionWeight5 ?? 0.4,
        projectionFinalSlot: res.data.data.projectionFinalSlot ?? "15:00",
      });
    } finally {
      setLoadingT0Schedule(false);
    }
  }

  async function loadMoneyFlowFeatures() {
    setLoadingMoneyFlowFeatures(true);
    try {
      const res = await apiClient.get<ApiEnvelope<MoneyFlowFeatureSetting>>("/admin/settings/money-flow-features");
      moneyFlowFeatureForm.setFieldsValue({
        historyBaselineDays: res.data.data.historyBaselineDays ?? 10,
        historyMinDaysForStable: res.data.data.historyMinDaysForStable ?? 3,
        historyAllowPartialBaseline: res.data.data.historyAllowPartialBaseline ?? true,
        intradaySlotMode: res.data.data.intradaySlotMode ?? "strict_same_slot",
        lowHistoryConfidenceMode: res.data.data.lowHistoryConfidenceMode ?? "flag_only",
      });
    } finally {
      setLoadingMoneyFlowFeatures(false);
    }
  }

  async function loadAll() {
    await Promise.all([loadDnse(), loadSsiFc(), loadMedia(), loadGoogleOauth(), loadHistorySchedule(), loadT0Schedule(), loadMoneyFlowFeatures()]);
  }

  useEffect(() => {
    void loadAll();
  }, []);

  async function saveAll() {
    setSavingAll(true);
    try {
      const [dnseValues, ssiFcValues, mediaValues, googleOauthValues, historyScheduleValues, t0ScheduleValues, moneyFlowFeatureValues] = await Promise.all([
        dnseForm.validateFields(),
        ssiFcForm.validateFields(),
        mediaForm.validateFields(),
        googleOauthForm.validateFields(),
        historyScheduleForm.validateFields(),
        t0ScheduleForm.validateFields(),
        moneyFlowFeatureForm.validateFields(),
      ]);

      await Promise.all([
        apiClient.put("/admin/settings/dnse", {
          apiKey: dnseValues.apiKey ?? "",
          apiSecret: dnseValues.apiSecret ?? "",
        }),
        apiClient.put("/admin/settings/ssi-fc", {
          consumerId: ssiFcValues.consumerId ?? "",
          consumerSecret: ssiFcValues.consumerSecret ?? "",
        }),
        apiClient.put("/admin/settings/media", mediaValues),
        apiClient.put("/admin/settings/google-oauth", {
          enabled: googleOauthValues.enabled ?? false,
          clientId: googleOauthValues.clientId ?? "",
          clientSecret: googleOauthValues.clientSecret ?? "",
        }),
        apiClient.put("/admin/settings/history-sync-schedule", {
          enabled: historyScheduleValues.enabled ?? false,
          hour: historyScheduleValues.hour ?? 0,
          minute: historyScheduleValues.minute ?? 0,
        }),
        apiClient.put("/admin/settings/t0-snapshot-schedule", {
          enabled: t0ScheduleValues.enabled ?? false,
          times: (t0ScheduleValues.times ?? []).filter(Boolean),
          foreignRefreshMinutes: t0ScheduleValues.foreignRefreshMinutes ?? 15,
          foreignStartTime: t0ScheduleValues.foreignStartTime ?? "09:15",
          foreignEndTime: t0ScheduleValues.foreignEndTime ?? "15:00",
          projectionSlots: (t0ScheduleValues.projectionSlots ?? []).filter(Boolean),
          projectionWindow20: t0ScheduleValues.projectionWindow20 ?? 20,
          projectionWindow5: t0ScheduleValues.projectionWindow5 ?? 5,
          projectionWeight20: t0ScheduleValues.projectionWeight20 ?? 0.6,
          projectionWeight5: t0ScheduleValues.projectionWeight5 ?? 0.4,
          projectionFinalSlot: t0ScheduleValues.projectionFinalSlot ?? "15:00",
        }),
        apiClient.put("/admin/settings/money-flow-features", {
          historyBaselineDays: moneyFlowFeatureValues.historyBaselineDays ?? 10,
          historyMinDaysForStable: moneyFlowFeatureValues.historyMinDaysForStable ?? 3,
          historyAllowPartialBaseline: moneyFlowFeatureValues.historyAllowPartialBaseline ?? true,
          intradaySlotMode: moneyFlowFeatureValues.intradaySlotMode ?? "strict_same_slot",
          lowHistoryConfidenceMode: moneyFlowFeatureValues.lowHistoryConfidenceMode ?? "flag_only",
        }),
      ]);

      await loadAll();
    } finally {
      setSavingAll(false);
    }
  }

  const loadingAny =
    loadingDnse || loadingSsiFc || loadingMedia || loadingGoogleOauth || loadingHistorySchedule || loadingT0Schedule || loadingMoneyFlowFeatures;

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Space style={{ width: "100%", justifyContent: "space-between" }} wrap>
        <Typography.Title level={3} style={{ margin: 0 }}>
          Settings
        </Typography.Title>
        <Button type="primary" onClick={() => void saveAll()} loading={savingAll} disabled={loadingAny}>
          Luu tat ca
        </Button>
      </Space>

      <Tabs
        items={[
          {
            key: "dnse",
            label: "DNSE",
            forceRender: true,
            children: <DnseTab form={dnseForm} loading={loadingDnse} />,
          },
          {
            key: "ssi-fc",
            label: "SSI FC",
            forceRender: true,
            children: <SsiFcTab form={ssiFcForm} loading={loadingSsiFc} />,
          },
          {
            key: "media",
            label: "Media",
            forceRender: true,
            children: <MediaTab form={mediaForm} loading={loadingMedia} />,
          },
          {
            key: "google-oauth",
            label: "Google OAuth",
            forceRender: true,
            children: <GoogleOauthTab form={googleOauthForm} loading={loadingGoogleOauth} />,
          },
          {
            key: "history-sync-schedule",
            label: "History Sync Schedule",
            forceRender: true,
            children: <HistorySyncScheduleTab form={historyScheduleForm} loading={loadingHistorySchedule} runtime={historyRuntime} />,
          },
          {
            key: "t0-snapshot-schedule",
            label: "T0 Snapshot Schedule",
            forceRender: true,
            children: <T0SnapshotScheduleTab form={t0ScheduleForm} loading={loadingT0Schedule} />,
          },
          {
            key: "money-flow-features",
            label: "Money Flow Features",
            forceRender: true,
            children: <MoneyFlowFeatureTab form={moneyFlowFeatureForm} loading={loadingMoneyFlowFeatures} />,
          },
        ]}
      />
    </Space>
  );
}
