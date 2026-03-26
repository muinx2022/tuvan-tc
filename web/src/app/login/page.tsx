"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { login, loginWithGoogle } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { GoogleSignInButton } from "@/components/auth/google-signin-button";
import { useRouter } from "next/navigation";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const auth = await login({ email, password });
      saveAuth(auth);
      router.push("/workspace");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function onGoogleLogin(credential: string) {
    setError("");
    try {
      const auth = await loginWithGoogle(credential);
      saveAuth(auth);
      router.push("/workspace");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel auth-panel-visual">
        <span className="eyebrow">Workspace access</span>
        <h1>Dang nhap de vao khu vuc lam viec cua MG/CTV</h1>
        <p>
          Luong auth da co email/password, refresh token va them dang nhap Google
          de vao workspace nhanh hon.
        </p>
        <div className="preview-stack">
          <div className="preview-card">
            <strong>Dashboard tong quan</strong>
            <span>Chi so thi truong, assets, alert</span>
          </div>
          <div className="preview-card">
            <strong>CRM & Watchlist</strong>
            <span>Khach hang, nhac viec, dong tien vao manh</span>
          </div>
        </div>
      </section>

      <section className="auth-panel auth-panel-form">
        <div className="auth-header">
          <span className="eyebrow">Dang nhap</span>
          <h2>Chao mung quay lai</h2>
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
          <label>
            Mat khau
            <input
              type="password"
              placeholder="Nhap mat khau"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <button type="submit" className="primary-button full-width" disabled={loading}>
            {loading ? "Dang xu ly..." : "Dang nhap"}
          </button>
        </form>

        <div className="divider">
          <span>Hoac</span>
        </div>

        <GoogleSignInButton onCredential={onGoogleLogin} />

        <div className="auth-links">
          <Link href="/forgot-password">Quen mat khau</Link>
          <Link href="/register">Tao tai khoan</Link>
          <Link href="/">Ve public site</Link>
        </div>

        {error ? <p className="error-banner">{error}</p> : null}
      </section>
    </main>
  );
}
