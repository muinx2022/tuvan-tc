import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Checkbox, Empty, Form, Input, Modal, Popconfirm, Space, Table, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";
import {
  getPermissionActionLabel,
  groupPermissions,
  splitPermissionCode,
  summarizePermissions,
  type PermissionGroup,
} from "../lib/rbac";

type Permission = {
  id: number;
  code: string;
  description?: string;
};

type RoleItem = {
  id: number;
  code: string;
  name: string;
  permissions: Permission[];
};

type RoleFormValues = {
  code: string;
  name: string;
};

const SYSTEM_ROLE_CODES = new Set(["ROLE_ADMIN", "ROLE_AUTHENTICATED"]);

function PermissionGroupEditor({
  group,
  selectedPermissionIds,
  onToggleGroup,
  onTogglePermission,
}: {
  group: PermissionGroup;
  selectedPermissionIds: number[];
  onToggleGroup: (groupIds: number[], checked: boolean) => void;
  onTogglePermission: (permissionId: number, checked: boolean) => void;
}) {
  const selectedSet = new Set(selectedPermissionIds);
  const selectedCount = group.permissions.filter((permission) => selectedSet.has(permission.id)).length;
  const checked = selectedCount === group.permissions.length;
  const indeterminate = selectedCount > 0 && selectedCount < group.permissions.length;

  return (
    <Card
      size="small"
      title={
        <Checkbox
          checked={checked}
          indeterminate={indeterminate}
          onChange={(event) => onToggleGroup(group.permissions.map((permission) => permission.id), event.target.checked)}
        >
          {group.label}
        </Checkbox>
      }
      extra={<Typography.Text type="secondary">{selectedCount}/{group.permissions.length} actions</Typography.Text>}
    >
      <Space wrap size={[8, 8]}>
        {group.permissions.map((permission) => {
          const { actionKey } = splitPermissionCode(permission.code);
          return (
            <Checkbox
              key={permission.id}
              checked={selectedSet.has(permission.id)}
              onChange={(event) => onTogglePermission(permission.id, event.target.checked)}
            >
              <Space size={4}>
                <span>{getPermissionActionLabel(actionKey)}</span>
                {permission.description ? <Typography.Text type="secondary">({permission.description})</Typography.Text> : null}
              </Space>
            </Checkbox>
          );
        })}
      </Space>
    </Card>
  );
}

export function RolesPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [roles, setRoles] = useState<RoleItem[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedPermissionIds, setSelectedPermissionIds] = useState<number[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<RoleItem | null>(null);
  const [form] = Form.useForm<RoleFormValues>();
  const permissionGroups = useMemo(() => groupPermissions(permissions), [permissions]);
  const selectedPermissions = useMemo(
    () => permissions.filter((permission) => selectedPermissionIds.includes(permission.id)),
    [permissions, selectedPermissionIds],
  );

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const [rolesRes, permissionsRes] = await Promise.all([
        apiClient.get<ApiEnvelope<RoleItem[]>>("/admin/rbac/roles"),
        apiClient.get<ApiEnvelope<Permission[]>>("/admin/rbac/permissions"),
      ]);
      setRoles(rolesRes.data.data);
      setPermissions(permissionsRes.data.data);
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Khong tai duoc permissions";
      setLoadError(apiMessage);
      message.error(apiMessage);
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
    setSelectedPermissionIds([]);
    setOpen(true);
  }

  function openEditModal(role: RoleItem) {
    setEditing(role);
    form.setFieldsValue({
      code: role.code,
      name: role.name,
    });
    setSelectedPermissionIds(role.permissions.map((item) => item.id));
    setOpen(true);
  }

  async function submit(values: RoleFormValues) {
    if (selectedPermissionIds.length === 0) {
      message.error("At least one permission is required");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        ...values,
        permissionIds: selectedPermissionIds,
      };
      if (editing) {
        await apiClient.put(`/admin/rbac/roles/${editing.id}`, payload);
        message.success("Cap nhat role thanh cong");
      } else {
        await apiClient.post("/admin/rbac/roles", payload);
        message.success("Tao role thanh cong");
      }
      setOpen(false);
      await load();
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Luu role that bai";
      message.error(apiMessage);
    } finally {
      setSaving(false);
    }
  }

  function toggleGroup(groupIds: number[], checked: boolean) {
    setSelectedPermissionIds((prev) => {
      const next = new Set(prev);
      for (const id of groupIds) {
        if (checked) {
          next.add(id);
        } else {
          next.delete(id);
        }
      }
      return Array.from(next).sort((left, right) => left - right);
    });
  }

  function togglePermission(permissionId: number, checked: boolean) {
    setSelectedPermissionIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(permissionId);
      } else {
        next.delete(permissionId);
      }
      return Array.from(next).sort((left, right) => left - right);
    });
  }

  async function remove(id: number) {
    try {
      await apiClient.delete(`/admin/rbac/roles/${id}`);
      message.success("Xoa role thanh cong");
      await load();
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Xoa role that bai";
      message.error(apiMessage);
    }
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Typography.Title level={3}>RBAC Roles</Typography.Title>
      <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
        Them role
      </Button>

      <Table<RoleItem>
        rowKey="id"
        loading={loading}
        dataSource={roles}
        columns={[
          { title: "ID", dataIndex: "id", width: 80 },
          { title: "Code", dataIndex: "code", width: 180 },
          { title: "Name", dataIndex: "name", width: 220 },
          {
            title: "Capabilities",
            render: (_, record) => (
              <Space direction="vertical" size={4}>
                {summarizePermissions(record.permissions).map((line) => (
                  <Typography.Text key={line}>{line}</Typography.Text>
                ))}
              </Space>
            ),
          },
          {
            title: "",
            width: 100,
            render: (_, record) =>
              SYSTEM_ROLE_CODES.has(record.code) ? null : (
                <Space>
                  <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
                  <Popconfirm
                    title="Xoa role nay?"
                    description="Role bi xoa se bi go khoi user"
                    okText="Xoa"
                    cancelText="Huy"
                    onConfirm={() => void remove(record.id)}
                  >
                    <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                  </Popconfirm>
                </Space>
              ),
          },
        ]}
      />

      <Modal
        title={editing ? "Cap nhat role" : "Them role"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
        width={920}
      >
        <Form<RoleFormValues> form={form} layout="vertical" onFinish={(values) => void submit(values)}>
          <Form.Item label="Code" name="code" rules={[{ required: true, message: "Role code is required" }]}>
            <Input placeholder="ROLE_CONTENT" />
          </Form.Item>
          <Form.Item label="Name" name="name" rules={[{ required: true, message: "Role name is required" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Permissions">
            <Space direction="vertical" style={{ width: "100%" }} size="middle">
              {loadError ? (
                <Alert
                  type="error"
                  showIcon
                  message={loadError}
                  action={
                    <Button size="small" onClick={() => void load()}>
                      Thu lai
                    </Button>
                  }
                />
              ) : null}
              <Space wrap>
                <Button onClick={() => setSelectedPermissionIds(permissions.map((permission) => permission.id))}>
                  Chon tat ca
                </Button>
                <Button onClick={() => setSelectedPermissionIds([])}>
                  Bo chon
                </Button>
                <Typography.Text type="secondary">
                  {selectedPermissionIds.length} actions duoc cap
                </Typography.Text>
              </Space>
              {permissionGroups.length === 0 ? (
                <Empty description={loadError ? "Khong tai duoc permissions" : "Chua co permissions"} />
              ) : (
                <Space direction="vertical" style={{ width: "100%", maxHeight: 420, overflow: "auto" }} size="small">
                  {permissionGroups.map((group) => (
                    <PermissionGroupEditor
                      key={group.key}
                      group={group}
                      selectedPermissionIds={selectedPermissionIds}
                      onToggleGroup={toggleGroup}
                      onTogglePermission={togglePermission}
                    />
                  ))}
                </Space>
              )}
              {selectedPermissions.length > 0 ? (
                <Card size="small" title="Preview capability">
                  <Space direction="vertical" size={4}>
                    {summarizePermissions(selectedPermissions).map((line) => (
                      <Typography.Text key={line}>{line}</Typography.Text>
                    ))}
                  </Space>
                </Card>
              ) : null}
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
