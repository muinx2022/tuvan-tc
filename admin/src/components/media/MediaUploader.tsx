import { UploadOutlined } from "@ant-design/icons";
import { Button, Upload } from "antd";
import type { UploadProps } from "antd";

type MediaUploaderProps = {
  label: string;
  accept?: string;
  onSelected: (file: File) => void;
};

export function MediaUploader({ label, accept, onSelected }: MediaUploaderProps) {
  const props: UploadProps = {
    accept,
    showUploadList: false,
    multiple: false,
    beforeUpload: (file) => {
      onSelected(file as File);
      return false;
    },
  };

  return (
    <Upload {...props}>
      <Button size="small" icon={<UploadOutlined />}>
        {label}
      </Button>
    </Upload>
  );
}
