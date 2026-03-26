"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { register } from "@/lib/api";
import { saveAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";

export default function RegisterPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const auth = await register({ fullName, email, password });
      saveAuth(auth);
      router.push("/workspace");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-panel auth-panel-visual alt">
        <span className="eyebrow">Tao tai khoan</span>
        <h1>Bien public traffic thanh workspace users</h1>
        <p>Tao tai khoan nhanh de vao ngay dashboard, bo loc dong tien va CRM khach hang.</p>
      </section>

      <section className="auth-panel auth-panel-form">
        <div className="auth-header">
          <span className="eyebrow">Dang ky</span>
          <h2>Khoi tao workspace</h2>
        </div>

        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Ho va ten
            <input
              type="text"
              placeholder="Nguyen Van A"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </label>
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
              placeholder="Toi thieu 6 ky tu"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={6}
              required
            />
          </label>
          <button type="submit" className="primary-button full-width" disabled={loading}>
            {loading ? "Dang tao..." : "Tao tai khoan"}
          </button>
        </form>

        <div className="auth-links">
          <Link href="/login">Da co tai khoan</Link>
          <Link href="/">Ve public site</Link>
        </div>

        {error ? <p className="error-banner">{error}</p> : null}
      </section>
    </main>
  );
}
