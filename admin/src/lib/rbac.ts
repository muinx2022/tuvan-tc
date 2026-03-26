export type PermissionItem = {
  id: number;
  code: string;
  description?: string;
};

export type PermissionGroup = {
  key: string;
  label: string;
  permissions: PermissionItem[];
};

const GROUP_LABELS: Record<string, string> = {
  admin: "Admin",
  "admin.portal": "Admin Portal",
  user: "Users",
  role: "Roles",
  post: "Posts",
  category: "Categories",
  settings: "Settings",
  authenticated: "Authentication",
};

const ACTION_LABELS: Record<string, string> = {
  view: "View",
  create: "Create",
  update: "Update",
  delete: "Delete",
  publish: "Publish",
  access: "Access",
};

function titleCase(value: string): string {
  return value
    .split(/[\s._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function splitPermissionCode(code: string): { groupKey: string; actionKey: string } {
  const parts = code.split(".");
  if (parts.length <= 1) {
    return { groupKey: "general", actionKey: code };
  }
  return {
    groupKey: parts.slice(0, -1).join("."),
    actionKey: parts[parts.length - 1],
  };
}

export function getPermissionGroupLabel(groupKey: string): string {
  return GROUP_LABELS[groupKey] ?? titleCase(groupKey);
}

export function getPermissionActionLabel(actionKey: string): string {
  return ACTION_LABELS[actionKey] ?? titleCase(actionKey);
}

export function groupPermissions(items: PermissionItem[]): PermissionGroup[] {
  const grouped = new Map<string, PermissionItem[]>();
  for (const item of items) {
    const { groupKey } = splitPermissionCode(item.code);
    const current = grouped.get(groupKey) ?? [];
    current.push(item);
    grouped.set(groupKey, current);
  }
  return Array.from(grouped.entries())
    .map(([key, permissions]) => ({
      key,
      label: getPermissionGroupLabel(key),
      permissions: [...permissions].sort((left, right) => left.code.localeCompare(right.code)),
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

export function summarizePermissions(items: PermissionItem[]): string[] {
  const grouped = groupPermissions(items);
  return grouped.map((group) => {
    const actions = group.permissions
      .map((permission) => getPermissionActionLabel(splitPermissionCode(permission.code).actionKey))
      .sort((left, right) => left.localeCompare(right));
    return `${group.label}: ${actions.join(", ")}`;
  });
}

export function mergeRolePermissions<
  T extends {
    id: number;
    permissions?: PermissionItem[];
  },
>(roles: T[], selectedRoleIds: number[]): PermissionItem[] {
  const byId = new Map<number, PermissionItem>();
  for (const role of roles) {
    if (!selectedRoleIds.includes(role.id)) {
      continue;
    }
    for (const permission of role.permissions ?? []) {
      byId.set(permission.id, permission);
    }
  }
  return Array.from(byId.values()).sort((left, right) => left.code.localeCompare(right.code));
}
