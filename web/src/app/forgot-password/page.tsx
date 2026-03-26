"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { forgotPassword } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    email: string;
    resetToken: string | null;
    expiresAt: string | null;
    tokenExposed: boolean;
  } | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await forgotPassword(email);
      setResult(response);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel auth-panel-visual">
        <span className="eyebrow">Forgot password</span>
        <h1>Tao lai duong vao workspace khi user quen mat khau</h1>
        <p>
          Backend da co API cap reset token. O che do MVP, token dang duoc expose de
          minh test nhanh tren local.
        </p>
      </section>

      <section className="auth-panel auth-panel-form">
        <div className="auth-header">
          <span className="eyebrow">Quen mat khau</span>
          <h2>Nhap email de nhan reset token</h2>
        </div>

        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Email
            <input
              type="email"
              placeholder="ban@congty.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="primary-button full-width" disabled={loading}>
            {loading ? "Dang tao token..." : "Gui yeu cau"}
          </button>
        </form>

        {result ? (
          <div className="info-card">
            <p>
              Neu email ton tai, reset token da duoc tao cho: <strong>{result.email}</strong>
            </p>
            {result.tokenExposed && result.resetToken ? (
              <Link
                href={`/reset-password?token=${encodeURIComponent(result.resetToken)}`}
                className="ghost-button"
              >
                Mo trang dat lai mat khau
              </Link>
            ) : (
              <p>Token dang duoc an, can noi voi email provider de gui link thuc te.</p>
            )}
          </div>
        ) : null}

        <div className="auth-links">
          <Link href="/login">Ve dang nhap</Link>
          <Link href="/">Ve public site</Link>
        </div>

        {error ? <p className="error-banner">{error}</p> : null}
      </section>
    </main>
  );
}
