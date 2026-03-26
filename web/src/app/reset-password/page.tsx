"use client";

import Link from "next/link";
import { FormEvent, Suspense, useMemo, useState } from "react";
import { resetPassword } from "@/lib/api";
import { useRouter, useSearchParams } from "next/navigation";

export const dynamic = "force-dynamic";

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<ResetPasswordSkeleton />}>
      <ResetPasswordContent />
    </Suspense>
  );
}

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = useMemo(() => searchParams.get("token") ?? "", [searchParams]);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!token) {
      setError("Reset token khong hop le");
      return;
    }

    if (password !== confirmPassword) {
      setError("Mat khau xac nhan chua khop");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, password);
      router.push("/login");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel auth-panel-visual alt">
        <span className="eyebrow">Reset password</span>
        <h1>Dat lai mat khau va quay ve login</h1>
        <p>Trang nay dung token tu API forgot password de cap nhat lai mat khau.</p>
      </section>

      <section className="auth-panel auth-panel-form">
        <div className="auth-header">
          <span className="eyebrow">Dat lai mat khau</span>
          <h2>Tao mat khau moi</h2>
        </div>

        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Mat khau moi
            <input
              type="password"
              placeholder="Toi thieu 6 ky tu"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={6}
              required
            />
          </label>
          <label>
            Xac nhan mat khau
            <input
              type="password"
              placeholder="Nhap lai mat khau"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              minLength={6}
              required
            />
          </label>
          <button type="submit" className="primary-button full-width" disabled={loading}>
            {loading ? "Dang cap nhat..." : "Cap nhat mat khau"}
          </button>
        </form>

        <div className="auth-links">
          <Link href="/forgot-password">Lay token moi</Link>
          <Link href="/login">Ve dang nhap</Link>
        </div>

        {error ? <p className="error-banner">{error}</p> : null}
      </section>
    </main>
  );
}

function ResetPasswordSkeleton() {
  return (
    <main className="auth-shell">
      <section className="auth-panel auth-panel-visual alt">
        <span className="eyebrow">Reset password</span>
        <h1>Dat lai mat khau va quay ve login</h1>
        <p>Dang tai thong tin reset token...</p>
      </section>

      <section className="auth-panel auth-panel-form">
        <div className="auth-header">
          <span className="eyebrow">Dat lai mat khau</span>
          <h2>Tao mat khau moi</h2>
        </div>
      </section>
    </main>
  );
}
