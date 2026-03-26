import Highlight from "@tiptap/extension-highlight";
import Image from "@tiptap/extension-image";
import Link from "@tiptap/extension-link";
import Placeholder from "@tiptap/extension-placeholder";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import StarterKit from "@tiptap/starter-kit";
import { Node, mergeAttributes } from "@tiptap/core";
import { EditorContent, useEditor } from "@tiptap/react";
import {
  BoldOutlined,
  CodeOutlined,
  FontSizeOutlined,
  HighlightOutlined,
  ItalicOutlined,
  LinkOutlined,
  OrderedListOutlined,
  RedoOutlined,
  StrikethroughOutlined,
  UndoOutlined,
  UnderlineOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import { Button, Divider, Space, Tooltip, Typography, theme as antdTheme } from "antd";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { uploadMedia } from "../../lib/media";
import { MediaUploader } from "../media/MediaUploader";
import "./RichTextEditor.css";

type PendingUpload = {
  id: string;
  file: File;
  assetType: "image" | "video" | "file";
  previewUrl: string;
  folder: string;
};

export type RichTextEditorHandle = {
  resolveContentBeforeSubmit: () => Promise<string>;
  clearPendingUploads: () => void;
};

const ExtendedImage = Image.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      uploadId: { default: null, parseHTML: (element) => element.getAttribute("data-upload-id") },
      originalFilename: { default: null, parseHTML: (element) => element.getAttribute("data-original-filename") },
    };
  },
  renderHTML({ HTMLAttributes }) {
    const { uploadId, originalFilename, ...rest } = HTMLAttributes;
    return [
      "img",
      mergeAttributes(rest, {
        ...(uploadId ? { "data-upload-id": uploadId } : {}),
        ...(originalFilename ? { "data-original-filename": originalFilename } : {}),
      }),
    ];
  },
});

const MediaVideo = Node.create({
  name: "mediaVideo",
  group: "block",
  atom: true,
  selectable: true,
  addAttributes() {
    return {
      src: { default: null },
      title: { default: null },
      uploadId: { default: null, parseHTML: (element) => element.getAttribute("data-upload-id") },
      originalFilename: { default: null, parseHTML: (element) => element.getAttribute("data-original-filename") },
    };
  },
  parseHTML() {
    return [{ tag: "div[data-media-video]" }];
  },
  renderHTML({ HTMLAttributes }) {
    const { src, title, uploadId, originalFilename } = HTMLAttributes;
    return [
      "div",
      {
        "data-media-video": "true",
        ...(uploadId ? { "data-upload-id": uploadId } : {}),
        ...(originalFilename ? { "data-original-filename": originalFilename } : {}),
      },
      ["video", { controls: "true", src, title }],
    ];
  },
});

function ActionButton({
  title,
  active,
  disabled,
  icon,
  onClick,
}: {
  title: string;
  active?: boolean;
  disabled?: boolean;
  icon: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <Tooltip title={title}>
      <Button type={active ? "primary" : "default"} size="small" icon={icon} disabled={disabled} onClick={onClick} />
    </Tooltip>
  );
}

export const RichTextEditor = forwardRef<RichTextEditorHandle, { value: string; onChange: (nextValue: string) => void; resetToken?: string | number }>(
  function RichTextEditor({ value, onChange, resetToken }, ref) {
    const { token } = antdTheme.useToken();
    const [pendingUploads, setPendingUploads] = useState<PendingUpload[]>([]);
    const pendingUploadsRef = useRef<PendingUpload[]>([]);

    const editor = useEditor({
      extensions: [
        StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
        Underline,
        Highlight.configure({ multicolor: true }),
        ExtendedImage.configure({ inline: false }),
        Link.configure({ openOnClick: false, autolink: true }),
        Placeholder.configure({ placeholder: "Viet noi dung, chen media, dinh dang tieu de..." }),
        TextAlign.configure({ types: ["heading", "paragraph"] }),
        MediaVideo,
      ],
      content: value,
      onUpdate: ({ editor: instance }) => onChange(instance.getHTML()),
    });

    useEffect(() => {
      if (!editor) {
        return;
      }
      if (editor.getHTML() !== value) {
        editor.commands.setContent(value || "", { emitUpdate: false });
      }
    }, [editor, value]);

    useEffect(() => {
      pendingUploadsRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
      pendingUploadsRef.current = [];
      setPendingUploads([]);
    }, [resetToken]);

    const queueUpload = (file: File, assetType: PendingUpload["assetType"], folder: string) => {
      if (!editor) {
        return;
      }
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const previewUrl = URL.createObjectURL(file);
      const pending: PendingUpload = { id, file, assetType, previewUrl, folder };
      const nextPending = [...pendingUploadsRef.current, pending];
      pendingUploadsRef.current = nextPending;
      setPendingUploads(nextPending);

      if (assetType === "image") {
        editor.chain().focus().insertContent({
          type: "image",
          attrs: { src: previewUrl, alt: file.name, uploadId: id, originalFilename: file.name },
        }).run();
        return;
      }
      if (assetType === "video") {
        editor.chain().focus().insertContent({
          type: "mediaVideo",
          attrs: { src: previewUrl, title: file.name, uploadId: id, originalFilename: file.name },
        }).run();
        return;
      }
      editor.chain().focus().insertContent(
        `<p><a href="${previewUrl}" target="_blank" data-upload-id="${id}" data-original-filename="${file.name}">${file.name}</a></p>`,
      ).run();
    };

    useImperativeHandle(ref, () => ({
      resolveContentBeforeSubmit: async () => {
        if (!editor) {
          return value;
        }
        let html = editor.getHTML();
        for (const pending of pendingUploadsRef.current) {
          const uploaded = await uploadMedia(pending.file, pending.folder);
          html = html.replaceAll(pending.previewUrl, uploaded.url);
          html = html.replaceAll(` data-upload-id="${pending.id}"`, "");
        }
        pendingUploadsRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
        pendingUploadsRef.current = [];
        setPendingUploads([]);
        editor.commands.setContent(html, { emitUpdate: false });
        onChange(html);
        return html;
      },
      clearPendingUploads: () => {
        pendingUploadsRef.current.forEach((item) => URL.revokeObjectURL(item.previewUrl));
        pendingUploadsRef.current = [];
        setPendingUploads([]);
      },
    }), [editor, onChange, value]);

    if (!editor) {
      return <div style={{ minHeight: 320, border: `1px solid ${token.colorBorder}`, borderRadius: 16 }} />;
    }

    return (
      <div
        className="post-editor"
        style={
          {
            ["--editor-bg" as string]: token.colorBgContainer,
            ["--editor-border" as string]: token.colorBorder,
            ["--editor-toolbar-bg" as string]: token.colorFillAlter,
            ["--editor-surface-bg" as string]: token.colorBgElevated,
            ["--editor-text" as string]: token.colorText,
            ["--editor-text-strong" as string]: token.colorTextHeading,
            ["--editor-placeholder" as string]: token.colorTextQuaternary,
            ["--editor-accent" as string]: token.colorPrimary,
            ["--editor-quote-bg" as string]: token.colorFillSecondary,
            ["--editor-code-bg" as string]: token.colorBgLayout,
            ["--editor-code-text" as string]: token.colorText,
            ["--editor-inline-code-bg" as string]: token.colorFillSecondary,
            ["--editor-shadow" as string]: token.boxShadowTertiary,
          } as React.CSSProperties
        }
      >
        <div className="post-editor__toolbar">
          <div className="post-editor__group">
            <ActionButton title="Heading 1" active={editor.isActive("heading", { level: 1 })} icon={<Typography.Text strong>H1</Typography.Text>} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()} />
            <ActionButton title="Heading 2" active={editor.isActive("heading", { level: 2 })} icon={<Typography.Text strong>H2</Typography.Text>} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} />
            <ActionButton title="Heading 3" active={editor.isActive("heading", { level: 3 })} icon={<FontSizeOutlined />} onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()} />
          </div>
          <div className="post-editor__group">
            <ActionButton title="Bold" active={editor.isActive("bold")} icon={<BoldOutlined />} onClick={() => editor.chain().focus().toggleBold().run()} />
            <ActionButton title="Italic" active={editor.isActive("italic")} icon={<ItalicOutlined />} onClick={() => editor.chain().focus().toggleItalic().run()} />
            <ActionButton title="Underline" active={editor.isActive("underline")} icon={<UnderlineOutlined />} onClick={() => editor.chain().focus().toggleUnderline().run()} />
            <ActionButton title="Strike" active={editor.isActive("strike")} icon={<StrikethroughOutlined />} onClick={() => editor.chain().focus().toggleStrike().run()} />
            <ActionButton title="Highlight" active={editor.isActive("highlight")} icon={<HighlightOutlined />} onClick={() => editor.chain().focus().toggleHighlight().run()} />
            <ActionButton title="Link" active={editor.isActive("link")} icon={<LinkOutlined />} onClick={() => {
              const url = window.prompt("Nhap link");
              if (url?.trim()) {
                editor.chain().focus().extendMarkRange("link").setLink({ href: url.trim() }).run();
              }
            }} />
          </div>
          <div className="post-editor__group">
            <ActionButton title="Bullet list" active={editor.isActive("bulletList")} icon={<UnorderedListOutlined />} onClick={() => editor.chain().focus().toggleBulletList().run()} />
            <ActionButton title="Ordered list" active={editor.isActive("orderedList")} icon={<OrderedListOutlined />} onClick={() => editor.chain().focus().toggleOrderedList().run()} />
            <ActionButton title="Quote" active={editor.isActive("blockquote")} icon={<Typography.Text>"</Typography.Text>} onClick={() => editor.chain().focus().toggleBlockquote().run()} />
            <ActionButton title="Code block" active={editor.isActive("codeBlock")} icon={<CodeOutlined />} onClick={() => editor.chain().focus().toggleCodeBlock().run()} />
          </div>
          <div className="post-editor__group">
            <MediaUploader label="Image" accept="image/*" onSelected={(file) => queueUpload(file, "image", "posts/images")} />
            <MediaUploader label="Video" accept="video/*" onSelected={(file) => queueUpload(file, "video", "posts/videos")} />
            <MediaUploader label="File" onSelected={(file) => queueUpload(file, "file", "posts/files")} />
          </div>
          <div className="post-editor__group">
            <ActionButton title="Undo" disabled={!editor.can().chain().focus().undo().run()} icon={<UndoOutlined />} onClick={() => editor.chain().focus().undo().run()} />
            <ActionButton title="Redo" disabled={!editor.can().chain().focus().redo().run()} icon={<RedoOutlined />} onClick={() => editor.chain().focus().redo().run()} />
          </div>
        </div>
        <div className="post-editor__surface">
          <EditorContent editor={editor} />
        </div>
        <Divider style={{ margin: 0 }} />
        <Space style={{ padding: "10px 16px" }} size="middle" wrap>
          <Typography.Text type="secondary">
            {pendingUploads.length > 0 ? `${pendingUploads.length} asset dang cho upload khi bam OK` : "Chon asset se tao preview tam, chi upload khi bam OK"}
          </Typography.Text>
        </Space>
      </div>
    );
  },
);
