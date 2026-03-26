export type MediaAsset = {
  provider: string;
  assetType: "image" | "video" | "file";
  url: string;
  publicId: string;
  originalFilename: string;
  contentType: string;
  size: number;
};

export async function uploadMedia(input: {
  file: File;
  token: string;
  apiBaseUrl?: string;
  folder?: string;
}) {
  const formData = new FormData();
  formData.append("file", input.file);
  if (input.folder?.trim()) {
    formData.append("folder", input.folder.trim());
  }

  const response = await fetch(`${input.apiBaseUrl ?? "http://localhost:8080/api/v1"}/admin/media/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${input.token}`,
    },
    body: formData,
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Upload failed");
  }

  const payload = (await response.json()) as { data: MediaAsset };
  return payload.data;
}
