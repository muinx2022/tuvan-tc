import { DeleteOutlined, EditOutlined, PlusOutlined } from "@ant-design/icons";
import { Alert, Button, Form, Input, Modal, Popconfirm, Select, Space, Table, Tag, Typography, message } from "antd";
import { useEffect, useMemo, useState } from "react";
import { apiClient, type ApiEnvelope } from "../lib/api";
import { mergeRolePermissions, summarizePermissions, type PermissionItem } from "../lib/rbac";

type User = {
  id: number;
  fullName: string;
  email: string;
  role: "ROLE_USER" | "ROLE_ADMIN" | "ROLE_AUTHENTICATED";
  rbacRoles: Array<{ id: number; code: string; name: string }>;
};

type RbacRole = {
  id: number;
  code: string;
  name: string;
  permissions: PermissionItem[];
};

type UserFormValues = {
  fullName: string;
  email: string;
  role: User["role"];
  password?: string;
  roleIds?: number[];
};

export function UsersPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [users, setUsers] = useState<User[]>([]);
  const [rbacRoles, setRbacRoles] = useState<RbacRole[]>([]);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const [form] = Form.useForm<UserFormValues>();
  const selectedRoleIds = Form.useWatch("roleIds", form) ?? [];
  const selectedSystemRole = Form.useWatch("role", form);
  const selectedPermissions = useMemo(
    () => mergeRolePermissions(rbacRoles, selectedRoleIds),
    [rbacRoles, selectedRoleIds],
  );
  const selectedCapabilitySummary = useMemo(
    () => summarizePermissions(selectedPermissions),
    [selectedPermissions],
  );

  async function load() {
    setLoading(true);
    try {
      const [usersRes, rolesRes] = await Promise.all([
        apiClient.get<ApiEnvelope<User[]>>("/admin/users"),
        apiClient.get<ApiEnvelope<RbacRole[]>>("/admin/rbac/roles"),
      ]);
      setUsers(usersRes.data.data);
      setRbacRoles(rolesRes.data.data);
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
    form.setFieldsValue({ role: "ROLE_USER", roleIds: [] });
    setOpen(true);
  }

  function openEditModal(user: User) {
    setEditing(user);
    form.setFieldsValue({
      fullName: user.fullName,
      email: user.email,
      role: user.role,
      password: "",
      roleIds: user.rbacRoles.map((item) => item.id),
    });
    setOpen(true);
  }

  async function submit(values: UserFormValues) {
    setSaving(true);
    try {
      if (editing) {
        await apiClient.put(`/admin/users/${editing.id}`, {
          fullName: values.fullName.trim(),
          email: values.email.trim(),
          role: values.role,
          password: values.password?.trim() ? values.password : undefined,
          roleIds: values.roleIds ?? [],
        });
        message.success("Cap nhat user thanh cong");
      } else {
        await apiClient.post("/admin/users", {
          fullName: values.fullName.trim(),
          email: values.email.trim(),
          role: values.role,
          password: values.password,
          roleIds: values.roleIds ?? [],
        });
        message.success("Tao user thanh cong");
      }
      setOpen(false);
      await load();
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Luu user that bai";
      message.error(apiMessage);
    } finally {
      setSaving(false);
    }
  }

  async function remove(id: number) {
    try {
      await apiClient.delete(`/admin/users/${id}`);
      message.success("Xoa user thanh cong");
      await load();
    } catch (error) {
      const apiMessage =
        (error as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        "Xoa user that bai";
      message.error(apiMessage);
    }
  }

  return (
    <Space direction="vertical" style={{ width: "100%" }}>
      <Typography.Title level={3}>Quản lý người dùng</Typography.Title>
      <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
        Them user
      </Button>
      <Table<User>
        loading={loading}
        rowKey="id"
        dataSource={users}
        columns={[
          { title: "ID", dataIndex: "id" },
          { title: "Họ tên", dataIndex: "fullName" },
          { title: "Email", dataIndex: "email" },
          {
            title: "Role hiện tại",
            dataIndex: "role",
            render: (role: User["role"]) => (
              <Tag color={role === "ROLE_ADMIN" ? "gold" : "blue"}>{role}</Tag>
            ),
          },
          {
            title: "RBAC roles",
            render: (_, record) => (
              <Space wrap size={[4, 4]}>
                {record.rbacRoles.length === 0 ? (
                  <Tag>None</Tag>
                ) : (
                  record.rbacRoles.map((rbacRole) => (
                    <Tag key={rbacRole.id}>{rbacRole.code}</Tag>
                  ))
                )}
              </Space>
            ),
          },
          {
            title: "Actions duoc cap",
            render: (_, record) => {
              if (record.role === "ROLE_ADMIN") {
                return <Tag color="gold">Full access</Tag>;
              }
              const permissions = mergeRolePermissions(rbacRoles, record.rbacRoles.map((item) => item.id));
              const summaries = summarizePermissions(permissions);
              if (record.role === "ROLE_USER") {
                summaries.unshift("Authentication: Access web");
              }
              return summaries.length > 0 ? (
                <Space direction="vertical" size={4}>
                  {summaries.map((line) => (
                    <Typography.Text key={`${record.id}-${line}`}>{line}</Typography.Text>
                  ))}
                </Space>
              ) : (
                <Typography.Text type="secondary">Chua duoc cap action nao</Typography.Text>
              );
            },
          },
          {
            title: "Action",
            render: (_, record) => (
              <Space>
                <Button type="text" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)} />
                <Popconfirm
                  title="Xoa user nay?"
                  description="Thao tac nay khong the hoan tac"
                  okText="Xoa"
                  cancelText="Huy"
                  onConfirm={() => void remove(record.id)}
                >
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} />
                </Popconfirm>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? "Cap nhat user" : "Them user"}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={() => form.submit()}
        confirmLoading={saving}
      >
        <Form<UserFormValues> form={form} layout="vertical" onFinish={(values) => void submit(values)}>
          <Form.Item label="Ho ten" name="fullName" rules={[{ required: true, message: "Full name is required" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Email" name="email" rules={[{ required: true, message: "Email is required" }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Role" name="role" rules={[{ required: true, message: "Role is required" }]}>
            <Select
              options={[
                { value: "ROLE_USER", label: "ROLE_USER" },
                { value: "ROLE_AUTHENTICATED", label: "ROLE_AUTHENTICATED" },
                { value: "ROLE_ADMIN", label: "ROLE_ADMIN" },
              ]}
            />
          </Form.Item>
          <Form.Item label="RBAC Roles" name="roleIds">
            <Select<number>
              mode="multiple"
              allowClear
              optionRender={(option) => {
                const role = rbacRoles.find((item) => item.id === option.value);
                const capabilityCount = role?.permissions.length ?? 0;
                return (
                  <Space direction="vertical" size={0}>
                    <Typography.Text strong>{option.label}</Typography.Text>
                    <Typography.Text type="secondary">{capabilityCount} actions</Typography.Text>
                  </Space>
                );
              }}
              options={rbacRoles.map((role) => ({ value: role.id, label: `${role.code} - ${role.name}` }))}
            />
          </Form.Item>
          <Form.Item label="Preview quyen">
            <Space direction="vertical" style={{ width: "100%" }} size="small">
              {selectedSystemRole === "ROLE_ADMIN" ? (
                <Alert type="success" showIcon message="ROLE_ADMIN co toan quyen, bo qua gioi han RBAC." />
              ) : null}
              {selectedCapabilitySummary.length > 0 ? (
                selectedCapabilitySummary.map((line) => (
                  <Typography.Text key={line}>{line}</Typography.Text>
                ))
              ) : (
                <Typography.Text type="secondary">
                  {selectedSystemRole === "ROLE_USER"
                    ? "User nay chi co quyen web co ban cho toi khi ban gan them RBAC roles."
                    : "Chua co action nao duoc cap tu RBAC roles."}
                </Typography.Text>
              )}
              {selectedSystemRole === "ROLE_USER" ? (
                <Typography.Text type="secondary">Mac dinh ROLE_USER van co quyen `authenticated.web`.</Typography.Text>
              ) : null}
            </Space>
          </Form.Item>
          <Form.Item
            label={editing ? "Password moi (bo trong neu khong doi)" : "Password"}
            name="password"
            rules={editing ? [] : [{ required: true, message: "Password is required" }]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
}
