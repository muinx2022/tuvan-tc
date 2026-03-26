import {
  DeleteOutlined,
  EditOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Select,
  Space,
  Switch,
  Table,
  Typography,
  message,
} from "antd";
import { useEffect, useRef, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";
import { RichTextEditor, type RichTextEditorHandle } from "../components/editor/RichTextEditor";

type Category = {
  id: number;
  name: string;
  slug: string;
};

type UserSummary = {
  id: number;
  fullName: string;
  email: string;
  role: string;
};

type PostItem = {
  id: number;
  title: string;
  slug: string;
  content: string | null;
  published: boolean;
  authorId: number;
  authorName: string;
  categoryIds: number[];
  createdAt: string;
  updatedAt: string;
};

type PostFormValues = {
  title: string;
  authorId?: number;
  published: boolean;
  categoryIds?: number[];
};

export function PostsPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [togglingPostId, setTogglingPostId] = useState<number | null>(null);
  const [items, setItems] = useState<PostItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [users, setUsers] = useState<UserSummary[]>([]);
  const [currentUserId, setCurrentUserId] = useState<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<PostItem | null>(null);
  const [contentHtml, setContentHtml] = useState("");
  const [editorResetToken, setEditorResetToken] = useState(0);
  const [categorySelectOpen, setCategorySelectOpen] = useState(false);
  const [hoveredPostId, setHoveredPostId] = useState<number | null>(null);
  const [form] = Form.useForm<PostFormValues>();
  const editorRef = useRef<RichTextEditorHandle | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [postRes, categoryRes, userRes] = await Promise.all([
        apiClient.get<ApiEnvelope<PostItem[]>>("/admin/posts"),
        apiClient.get<ApiEnvelope<Category[]>>("/admin/categories"),
        apiClient.get<ApiEnvelope<UserSummary[]>>("/admin/users"),
      ]);
      setItems(postRes.data.data);
      setCategories(categoryRes.data.data);
      setUsers(userRes.data.data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const raw = localStorage.getItem("admin_user");
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as { userId?: number };
        if (parsed.userId) {
          setCurrentUserId(parsed.userId);
        }
      } catch {
        // ignore malformed localStorage payload
      }
    }
    void load();
  }, []);

  function openCreateModal() {
    setEditing(null);
    form.setFieldsValue({
      title: "",
      authorId: currentUserId ?? users[0]?.id,
      published: false,
      categoryIds: [],
    });
    setContentHtml("");
    setEditorResetToken((prev) => prev + 1);
    setOpen(true);
  }

  function openEditModal(record: PostItem) {
    setEditing(record);
    form.setFieldsValue({
      title: record.title,
      authorId: record.authorId,
      published: record.published,
      categoryIds: record.categoryIds,
    });
    setContentHtml(record.content ?? "");
    setEditorResetToken((prev) => prev + 1);
    setOpen(true);
  }

  async function submit(values: PostFormValues) {
    setSaving(true);
    try {
      const resolvedContentHtml = await editorRef.current?.resolveContentBeforeSubmit() ?? contentHtml ?? "";
      const payload = {
        title: values.title.trim(),
        content: resolvedContentHtml,
        authorId: values.authorId,
        published: values.published ?? false,
        categoryIds: values.categoryIds ?? [],
      };
      if (editing) {
        await apiClient.put(`/admin/posts/${editing.id}`, payload);
      } else {
        await apiClient.post("/admin/posts", payload);
      }
      setOpen(false);
      await load();
      message.success(editing ? "Cap nhat post thanh cong" : "Tao post thanh cong");
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Luu post that bai";
      message.error(apiMessage);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    await apiClient.delete(`/admin/posts/${id}`);
    await load();
  }

  async function togglePublished(record: PostItem, checked: boolean) {
    setTogglingPostId(record.id);
    try {
      await apiClient.put(`/admin/posts/${record.id}`, {
        title: record.title,
        content: record.content ?? "",
        authorId: record.authorId,
        published: checked,
        categoryIds: record.categoryIds,
      });
      setItems((prev) =>
        prev.map((item) => (item.id === record.id ? { ...item, published: checked } : item)),
      );
      message.success(checked ? "Da publish post" : "Da unpublish post");
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Cap nhat status that bai";
      message.error(apiMessage);
    } finally {
      setTogglingPostId(null);
    }
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3}>Quan ly post</Typography.Title>
      <Card>
        <Button type="primary" onClick={openCreateModal}>
          Them post
        </Button>
      </Card>
      <Table<PostItem>
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={[
          { title: "ID", dataIndex: "id", width: 80 },
          {
            title: "Title",
            render: (_, record) => (
              <Space direction="vertical" size={0}>
                <Button
                  type="link"
                  style={{ padding: 0, height: "auto" }}
                  onClick={() => openEditModal(record)}
                >
                  {record.title}
                </Button>
                <Typography.Text type="secondary">{record.slug}</Typography.Text>
              </Space>
            ),
          },
          { title: "Author", dataIndex: "authorName" },
          {
            title: "Status",
            render: (_, record) => (
              <Switch
                size="small"
                checked={record.published}
                loading={togglingPostId === record.id}
                onChange={(checked) => void togglePublished(record, checked)}
              />
            ),
          },
          {
            title: "Categories",
            render: (_, record) => {
              const names = record.categoryIds
                .map((id) => categories.find((category) => category.id === id)?.name)
                .filter((name): name is string => Boolean(name));
              return names.length > 0 ? names.join(", ") : "-";
            },
          },
          {
            title: "Updated",
            dataIndex: "updatedAt",
            render: (value: string) => new Date(value).toLocaleString(),
          },
          {
            title: "",
            width: 96,
            render: (_, record) => (
              hoveredPostId === record.id ? (
                <Space>
                  <Button
                    type="text"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => openEditModal(record)}
                  />
                  <Popconfirm title="Xoa post nay?" onConfirm={() => void remove(record.id)}>
                    <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ) : null
            ),
          },
        ]}
        onRow={(record) => ({
          onMouseEnter: () => setHoveredPostId(record.id),
          onMouseLeave: () => setHoveredPostId((prev) => (prev === record.id ? null : prev)),
        })}
      />

      <Modal
        title={editing ? "Cap nhat post" : "Them post"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        width={720}
      >
        <Form<PostFormValues>
          form={form}
          layout="vertical"
          onFinish={(values) => void submit(values)}
          initialValues={{ published: false, categoryIds: [] }}
        >
          <Form.Item label="Title" name="title" rules={[{ required: true, message: "Title is required" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Author" name="authorId" rules={[{ required: true, message: "Author is required" }]}>
            <Select<number>
              showSearch
              optionFilterProp="label"
              options={users.map((item) => ({
                value: item.id,
                label: `${item.fullName} (${item.email})`,
              }))}
            />
          </Form.Item>
          <Form.Item label="Content">
            <RichTextEditor ref={editorRef} value={contentHtml} onChange={setContentHtml} resetToken={editorResetToken} />
          </Form.Item>
          <Form.Item label="Categories" name="categoryIds">
            <Select<number>
              mode="multiple"
              allowClear
              open={categorySelectOpen}
              onOpenChange={setCategorySelectOpen}
              onSelect={() => setCategorySelectOpen(false)}
              options={categories.map((item) => ({ value: item.id, label: `${item.name} (#${item.id})` }))}
            />
          </Form.Item>
          <Form.Item label="Published" name="published" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
