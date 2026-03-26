import { useLogin } from "@refinedev/core";
import { BulbOutlined, MoonOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Checkbox, Form, Input, Switch, Typography } from "antd";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";

type LoginPageProps = {
  isDark?: boolean;
  onToggleTheme?: (checked: boolean) => void;
};

export function LoginPage({ isDark = false, onToggleTheme }: LoginPageProps) {
  const { mutateAsync, isPending } = useLogin<{ email: string; password: string; rememberMe: boolean }>();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const reason = new URLSearchParams(location.search).get("reason");
    if (reason === "session-expired") {
      setError("Session da het han. Vui long dang nhap lai.");
    }
  }, [location.search]);

  return (
    <div className={`login-shell ${isDark ? "login-shell-dark" : ""}`}>
      <div className="login-theme-toggle">
        <MoonOutlined />
        <Switch
          size="small"
          checked={isDark}
          onChange={(checked) => onToggleTheme?.(checked)}
          checkedChildren={<BulbOutlined />}
          unCheckedChildren={<BulbOutlined />}
        />
      </div>

      <Card title="Admin Login" className="login-card">
        <Form
          layout="vertical"
          initialValues={{ rememberMe: true }}
          onFinish={async (values) => {
            setError(null);
            const result = await mutateAsync(values);
            if (result?.success) {
              navigate(result.redirectTo ?? "/dashboard", { replace: true });
              return;
            }

            if (!result || result.success === false) {
              setError(result?.error?.message ?? "Dang nhap that bai");
            }
          }}
        >
          <Form.Item label="Email" name="email" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item label="Password" name="password" rules={[{ required: true }]}>
            <Input.Password />
          </Form.Item>
          <Form.Item name="rememberMe" valuePropName="checked" style={{ marginBottom: 12 }}>
            <Checkbox>Remember me</Checkbox>
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={isPending} block>
            Dang nhap
          </Button>
        </Form>
        {error ? <Alert type="error" message={error} style={{ marginTop: 12 }} /> : null}
        <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
          Luu y: chi tai khoan co ROLE_ADMIN moi dang nhap duoc.
        </Typography.Paragraph>
      </Card>
    </div>
  );
}
