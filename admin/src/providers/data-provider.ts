import type { DataProvider } from "@refinedev/core";
import { apiClient, apiUrl } from "../lib/api";
import type { ApiEnvelope } from "../lib/api";

function endpoint(resource: string): string {
  if (resource === "users") {
    return "/admin/users";
  }
  return `/${resource}`;
}

export const dataProvider: DataProvider = {
  getApiUrl: () => apiUrl,

  getList: async ({ resource }) => {
    const res = await apiClient.get<ApiEnvelope<unknown[]>>(endpoint(resource));
    const data = res.data.data;
    return {
      data: data.map((item) => ({ ...(item as Record<string, unknown>) })),
      total: data.length,
    } as any;
  },

  getOne: async ({ resource, id }) => {
    const res = await apiClient.get<ApiEnvelope<Record<string, unknown>>>(
      `${endpoint(resource)}/${id}`,
    );
    return { data: res.data.data } as any;
  },

  create: async ({ resource, variables }) => {
    const res = await apiClient.post<ApiEnvelope<Record<string, unknown>>>(
      endpoint(resource),
      variables,
    );
    return { data: res.data.data } as any;
  },

  update: async ({ resource, id, variables }) => {
    if (resource === "users") {
      const res = await apiClient.patch<ApiEnvelope<Record<string, unknown>>>(
        `${endpoint(resource)}/${id}/role`,
        variables,
      );
      return { data: res.data.data } as any;
    }
    const res = await apiClient.put<ApiEnvelope<Record<string, unknown>>>(
      `${endpoint(resource)}/${id}`,
      variables,
    );
    return { data: res.data.data } as any;
  },

  deleteOne: async ({ resource, id }) => {
    await apiClient.delete(`${endpoint(resource)}/${id}`);
    return { data: { id } } as any;
  },

  getMany: async ({ resource, ids }) => {
    const res = await apiClient.get<ApiEnvelope<Record<string, unknown>[]>>(endpoint(resource));
    return {
      data: res.data.data.filter((item) => ids.includes(item.id as string | number)),
    } as any;
  },

  custom: async ({ url, method, payload, query }) => {
    const res = await apiClient.request({
      url,
      method,
      data: payload,
      params: query,
    });
    return { data: res.data } as any;
  },
};
