import { DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { Button, Card, Form, Input, Modal, Select, Space, Switch, Tree, Typography, message } from "antd";
import type { DataNode, TreeProps } from "antd/es/tree";
import { useEffect, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";

type Category = {
  id: number;
  name: string;
  slug: string;
  published: boolean;
  parentId: number | null;
  sortOrder: number;
  createdAt: string;
  updatedAt: string;
};

type CategoryFormValues = {
  name: string;
  parentId?: number;
};

type CategoryTreeNode = {
  id: number;
  name: string;
  slug: string;
  published: boolean;
  parentId: number | null;
  sortOrder: number;
  children: CategoryTreeNode[];
};

export function CategoriesPage() {
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<Category[]>([]);
  const [tree, setTree] = useState<CategoryTreeNode[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [savingTree, setSavingTree] = useState(false);
  const [togglingCategoryId, setTogglingCategoryId] = useState<number | null>(null);
  const [hoveredCategoryId, setHoveredCategoryId] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [form] = Form.useForm<CategoryFormValues>();

  async function load() {
    setLoading(true);
    try {
      const [listRes, treeRes] = await Promise.all([
        apiClient.get<ApiEnvelope<Category[]>>("/admin/categories"),
        apiClient.get<ApiEnvelope<CategoryTreeNode[]>>("/admin/categories/tree"),
      ]);
      setItems(listRes.data.data);
      setTree(treeRes.data.data);
      setExpandedKeys(collectKeys(treeRes.data.data));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openCreateModal() {
    setEditing(null);
    form.resetFields();
    setOpen(true);
  }

  function openEditModal(record: Category) {
    setEditing(record);
    form.setFieldsValue({
      name: record.name,
      parentId: record.parentId ?? undefined,
    });
    setOpen(true);
  }

  async function submit(values: CategoryFormValues) {
    setSaving(true);
    try {
      const payload = {
        name: values.name.trim(),
        parentId: values.parentId ?? null,
      };
      if (editing) {
        await apiClient.put(`/admin/categories/${editing.id}`, payload);
      } else {
        await apiClient.post("/admin/categories", payload);
      }
      setOpen(false);
      await load();
      message.success(editing ? "Cap nhat category thanh cong" : "Them category thanh cong");
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Luu category that bai";
      message.error(apiMessage);
    } finally {
      setSaving(false);
    }
  }

  function toDataNodes(nodes: CategoryTreeNode[]): DataNode[] {
    return nodes.map((node) => ({
      key: String(node.id),
      title: renderTitle(node),
      children: toDataNodes(node.children),
    }));
  }

  async function remove(id: number) {
    try {
      await apiClient.delete(`/admin/categories/${id}`);
      message.success("Da xoa category va toan bo sub category");
      await load();
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Xoa category that bai";
      message.error(apiMessage);
    }
  }

  function confirmDelete(id: number) {
    Modal.confirm({
      centered: true,
      title: "Xoa category nay?",
      content: "Thao tac nay se xoa category duoc chon va toan bo nhanh con (sub categories).",
      okText: "Xoa",
      cancelText: "Huy",
      okButtonProps: { danger: true },
      onOk: async () => {
        await remove(id);
      },
    });
  }

  async function togglePublished(node: CategoryTreeNode, checked: boolean) {
    setTogglingCategoryId(node.id);
    try {
      await apiClient.patch(`/admin/categories/${node.id}/status`, { published: checked });
      const updateTree = (list: CategoryTreeNode[]): CategoryTreeNode[] =>
        list.map((item) => ({
          ...item,
          published: item.id === node.id ? checked : item.published,
          children: updateTree(item.children),
        }));
      setTree((prev) => updateTree(prev));
      setItems((prev) => prev.map((item) => (item.id === node.id ? { ...item, published: checked } : item)));
      message.success(checked ? "Da publish category" : "Da unpublish category");
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Cap nhat status that bai";
      message.error(apiMessage);
    } finally {
      setTogglingCategoryId(null);
    }
  }

  function renderTitle(node: CategoryTreeNode) {
    const category = items.find((item) => item.id === node.id);
    return (
      <div
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}
        onMouseEnter={() => setHoveredCategoryId(node.id)}
        onMouseLeave={() => setHoveredCategoryId((prev) => (prev === node.id ? null : prev))}
      >
        <Button
          type="link"
          style={{ padding: 0, height: "auto" }}
          onClick={(event) => {
            event.stopPropagation();
            if (category) {
              openEditModal(category);
            }
          }}
        >
          {node.name} <Typography.Text type="secondary">({node.slug})</Typography.Text>
        </Button>
        <Space
          onClick={(event) => event.stopPropagation()}
          size="small"
        >
          <Switch
            size="small"
            checked={node.published}
            loading={togglingCategoryId === node.id}
            onChange={(checked) => void togglePublished(node, checked)}
          />
          <Space
            size="small"
            style={{ visibility: hoveredCategoryId === node.id ? "visible" : "hidden" }}
          >
            <Button
              type="text"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                if (category) {
                  openEditModal(category);
                }
              }}
            />
            <Button
              type="text"
              danger
              size="small"
              icon={<DeleteOutlined />}
              onClick={() => confirmDelete(node.id)}
            />
          </Space>
        </Space>
      </div>
    );
  }

  function collectKeys(nodes: CategoryTreeNode[]): string[] {
    const keys: string[] = [];
    const loop = (itemsToWalk: CategoryTreeNode[]) => {
      itemsToWalk.forEach((item) => {
        keys.push(String(item.id));
        if (item.children.length > 0) {
          loop(item.children);
        }
      });
    };
    loop(nodes);
    return keys;
  }

  function flattenTree(nodes: CategoryTreeNode[], parentId: number | null, rows: Category[]) {
    nodes.forEach((node, index) => {
      rows.push({
        id: node.id,
        name: node.name,
        slug: node.slug,
        published: node.published,
        parentId,
        sortOrder: index,
        createdAt: "",
        updatedAt: "",
      });
      flattenTree(node.children, node.id, rows);
    });
  }

  async function persistTree(nextTree: CategoryTreeNode[]) {
    const rows: Category[] = [];
    flattenTree(nextTree, null, rows);
    setSavingTree(true);
    try {
      await apiClient.put("/admin/categories/tree", rows.map((row) => ({
        id: row.id,
        parentId: row.parentId,
        sortOrder: row.sortOrder,
      })));
      message.success("Da cap nhat tree");
      await load();
    } catch {
      message.error("Cap nhat tree that bai");
      await load();
    } finally {
      setSavingTree(false);
    }
  }

  const onDrop: TreeProps["onDrop"] = (info) => {
    const dropKey = String(info.node.key);
    const dragKey = String(info.dragNode.key);
    const dropPos = info.node.pos.split("-");
    const dropPosition = info.dropPosition - Number(dropPos[dropPos.length - 1]);

    const deepCopy = (nodes: CategoryTreeNode[]): CategoryTreeNode[] =>
      nodes.map((item) => ({ ...item, children: deepCopy(item.children) }));
    const data = deepCopy(tree);

    let dragObj: CategoryTreeNode | undefined;
    const loop = (
      list: CategoryTreeNode[],
      key: string,
      callback: (node: CategoryTreeNode, index: number, arr: CategoryTreeNode[]) => void,
    ) => {
      for (let i = 0; i < list.length; i += 1) {
        if (String(list[i].id) === key) {
          callback(list[i], i, list);
          return;
        }
        if (list[i].children.length > 0) {
          loop(list[i].children, key, callback);
        }
      }
    };

    loop(data, dragKey, (item, index, arr) => {
      arr.splice(index, 1);
      dragObj = item;
    });
    if (!dragObj) {
      return;
    }

    if (!info.dropToGap) {
      loop(data, dropKey, (item) => {
        item.children = item.children || [];
        item.children.unshift(dragObj!);
      });
    } else if ((info.node as DataNode).children?.length && info.node.expanded && dropPosition === 1) {
      loop(data, dropKey, (item) => {
        item.children = item.children || [];
        item.children.unshift(dragObj!);
      });
    } else {
      let targetArr: CategoryTreeNode[] = [];
      let targetIndex = 0;
      loop(data, dropKey, (_item, index, arr) => {
        targetArr = arr;
        targetIndex = index;
      });
      if (dropPosition === -1) {
        targetArr.splice(targetIndex, 0, dragObj);
      } else {
        targetArr.splice(targetIndex + 1, 0, dragObj);
      }
    }

    setTree(data);
    void persistTree(data);
  };

  return (
    <Space direction="vertical" style={{ width: "100%" }} size="large">
      <Typography.Title level={3}>Quan ly category</Typography.Title>
      <Card>
        <Button type="primary" onClick={openCreateModal} loading={loading}>
          Them category
        </Button>
      </Card>
      <Card title="Tree category (drag drop de doi parent va thu tu)">
        {savingTree ? <Typography.Text type="secondary">Dang luu thay doi tree...</Typography.Text> : null}
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, padding: "0 8px" }}>
          <Typography.Text type="secondary">Title</Typography.Text>
          <Space size={24}>
            <Typography.Text type="secondary">Status</Typography.Text>
            <Typography.Text type="secondary">Action</Typography.Text>
          </Space>
        </div>
        <Tree
          blockNode
          draggable
          treeData={toDataNodes(tree)}
          onDrop={onDrop}
          expandedKeys={expandedKeys}
          onExpand={(keys) => setExpandedKeys(keys.map((key) => String(key)))}
        />
      </Card>

      <Modal
        title={editing ? "Cap nhat category" : "Them category"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
      >
        <Form<CategoryFormValues> form={form} layout="vertical" onFinish={(values) => void submit(values)}>
          <Form.Item label="Name" name="name" rules={[{ required: true, message: "Name is required" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Parent" name="parentId">
            <Select<number>
              allowClear
              placeholder="Chon parent category"
              options={items
                .filter((item) => !editing || item.id !== editing.id)
                .map((item) => ({ value: item.id, label: `${item.name} (#${item.id})` }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
