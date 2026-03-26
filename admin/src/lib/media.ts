import { apiClient, type ApiEnvelope } from "./api";

export type MediaProvider = "local" | "cloudinary" | "cloudflare_s3";

export type MediaAsset = {
  provider: string;
  assetType: "image" | "video" | "file";
  url: string;
  publicId: string;
  originalFilename: string;
  contentType: string;
  size: number;
};

export type MediaSetting = {
  id: number;
  provider: MediaProvider;
  localRootPath: string | null;
  localPublicBaseUrl: string | null;
  cloudinaryCloudName: string | null;
  cloudinaryApiKey: string | null;
  cloudinaryApiSecret: string | null;
  cloudinaryFolder: string | null;
  cloudflareS3Endpoint: string | null;
  cloudflareS3AccessKey: string | null;
  cloudflareS3SecretKey: string | null;
  cloudflareS3Bucket: string | null;
  cloudflareS3Region: string | null;
  cloudflareS3PublicBaseUrl: string | null;
  updatedAt: string;
};

export type MediaSettingFormValues = {
  provider: MediaProvider;
  localRootPath?: string;
  localPublicBaseUrl?: string;
  cloudinaryCloudName?: string;
  cloudinaryApiKey?: string;
  cloudinaryApiSecret?: string;
  cloudinaryFolder?: string;
  cloudflareS3Endpoint?: string;
  cloudflareS3AccessKey?: string;
  cloudflareS3SecretKey?: string;
  cloudflareS3Bucket?: string;
  cloudflareS3Region?: string;
  cloudflareS3PublicBaseUrl?: string;
};

export async function uploadMedia(file: File, folder?: string) {
  const formData = new FormData();
  formData.append("file", file);
  if (folder?.trim()) {
    formData.append("folder", folder.trim());
  }
  const response = await apiClient.post<ApiEnvelope<MediaAsset>>("/admin/media/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data.data;
}
