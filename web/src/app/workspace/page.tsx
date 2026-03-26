"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { me } from "@/lib/api";
import { clearAuth, getUser } from "@/lib/auth";
import { workspaceNav } from "@/lib/portal-data";
import type { NavItem } from "@/lib/portal-data";
import type { UserSummary } from "@/lib/types";
import { useRouter } from "next/navigation";

/* ─── Dashboard mock data ────────────────────────────────── */

const industryRows = [
  { name: "Chung khoan", value: "4.82T", change: "+12.4%", up: true },
  { name: "Bat dong san", value: "3.21T", change: "+7.1%", up: true },
  { name: "Ngan hang", value: "2.98T", change: "-2.3%", up: false },
  { name: "Dau khi", value: "1.64T", change: "+5.8%", up: true },
  { name: "Cong nghe", value: "0.97T", change: "-1.1%", up: false },
  { name: "Ban le", value: "0.73T", change: "+3.2%", up: true },
];

const tickerRows = [
  { ticker: "SSI", name: "Chung khoan SSI", desc: "Dong tien vao manh, nen tang gia giu duoc", rs: "92" },
  { ticker: "VCI", name: "Viet Capital Sec", desc: "Tang dot bien khoi luong, nhom chu y", rs: "88" },
  { ticker: "VIX", name: "Chung khoan VIX", desc: "Breakout khoi vung tich luy 3 thang", rs: "85" },
  { ticker: "HCM", name: "HCMC Securities", desc: "Dong tien ngoai vao manh, duy tri", rs: "81" },
  { ticker: "FTS", name: "Chung khoan FPT", desc: "Theo doi nguong ho tro quan trong", rs: "76" },
];

const chartLabels = ["T2", "T3", "T4", "T5", "T6", "T7", "CN", "T2", "T3", "T4", "T5", "T6"];

/* ─── Sidebar nav renderer ───────────────────────────────── */

/** Level-1 leaf row (no children) */
function NavLeaf({ item, deep = false }: { item: NavItem; deep?: boolean }) {
  return (
    <div className={deep ? "sl-leaf sl-leaf--deep" : "sl-leaf"}>
      {item.icon
        ? <span className="sl-leaf-icon">{item.icon}</span>
        : <span className="sl-leaf-dot" />
      }
      <span className="sl-leaf-label">{item.label}</span>
      {item.badge && <span className="sl-badge">{item.badge}</span>}
    </div>
  );
}

/** Level-1 sub-section that has further children */
function NavMid({ item }: { item: NavItem }) {
  return (
    <div className="sl-mid">
      <div className="sl-mid-row">
        {item.icon && <span className="sl-mid-icon">{item.icon}</span>}
        <span className="sl-mid-label">{item.label}</span>
        {item.badge && <span className="sl-badge">{item.badge}</span>}
      </div>
      {item.children && item.children.length > 0 && (
        <div className="sl-mid-children">
          {item.children.map((c) => (
            <NavLeaf key={c.label} item={c} deep />
          ))}
        </div>
      )}
    </div>
  );
}

/** Level-0 section group */
function NavGroup({ item, active = false }: { item: NavItem; active?: boolean }) {
  return (
    <div className="sl-group">
      {/* Group header */}
      <div className={active ? "sl-group-head sl-group-head--active" : "sl-group-head"}>
        {item.icon && <span className="sl-group-icon">{item.icon}</span>}
        {item.href
          ? <Link href={item.href} className="sl-group-label">{item.label}</Link>
          : <span className="sl-group-label">{item.label}</span>
        }
        {item.badge && <span className="sl-badge sl-badge--warn">{item.badge}</span>}
      </div>

      {/* Children */}
      {item.children && item.children.length > 0 && (
        <div className="sl-group-body">
          {item.children.map((child) =>
            child.children && child.children.length > 0
              ? <NavMid key={child.label} item={child} />
              : <NavLeaf key={child.label} item={child} />
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Page ───────────────────────────────────────────────── */

export default function WorkspacePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getUser()) { router.push("/login"); return; }
    void me().then(setProfile).catch((err: Error) => setError(err.message));
  }, [router]);

  function onLogout() { clearAuth(); router.push("/login"); }

  return (
    <main className="workspace-shell">

      {/* ════════════════════════════════════════════════════
          SIDEBAR
      ════════════════════════════════════════════════════ */}
      <aside className="left-rail">

        {/* ── Brand ──────────────────────────── */}
        <div className="sl-brand">
          <div className="sl-brand-logo">
            <span>MG</span>
          </div>
          <div className="sl-brand-text">
            <strong>Ban lam viec</strong>
            <span>MG / CTV Workspace</span>
          </div>
        </div>

        {/* ── User chip ──────────────────────── */}
        <div className="sl-user">
          <div className="sl-avatar">{profile?.fullName?.charAt(0) ?? "U"}</div>
          <div className="sl-user-info">
            <strong>{profile?.fullName ?? "Dang tai..."}</strong>
            <span>{profile?.email ?? "—"}</span>
          </div>
          <span className="sl-user-badge">MG</span>
        </div>

        {/* ── Nav (scrollable) ───────────────── */}
        <nav className="sl-nav">
          {workspaceNav.map((group, i) => (
            <NavGroup key={group.label} item={group} active={i === 0} />
          ))}
        </nav>

        {/* ── Footer ─────────────────────────── */}
        <div className="sl-footer">
          <button type="button" className="sl-logout" onClick={onLogout}>
            <span>↩</span> Dang xuat
          </button>
        </div>

      </aside>

      {/* ════════════════════════════════════════════════════
          MAIN CONTENT
      ════════════════════════════════════════════════════ */}
      <section className="workspace-content">

        {/* Topbar */}
        <header className="workspace-topbar">
          <div>
            <span className="eyebrow">Dashboard</span>
            <h2>Trung tam phan tich dong tien &amp; CRM</h2>
          </div>
          <div className="chip-row">
            <span className="pill up">▲ VNI +1.28%</span>
            <span className="pill up">VN30 Manh</span>
            <span className="pill warn">AUM Tang</span>
            <span className="pill">GTGD 14.2K ty</span>
          </div>
        </header>

        {error ? <p className="error-banner">{error}</p> : null}

        <section className="board-grid">

          {/* Metrics */}
          <article className="board-card hero-span">
            <div className="card-head">
              <h3>Cac chi so &amp; assets</h3>
              <span className="muted">Realtime snapshot</span>
            </div>
            <div className="metrics-row">
              {[
                { label: "Tong khach hang", value: "328", change: "▲ +12 thang nay", up: true },
                { label: "Tong tai san AUM", value: "128.5B", change: "▲ +8.3%", up: true },
                { label: "Khach hang moi", value: "18", change: "▲ +5 tuan nay", up: true },
                { label: "Canh bao cat lo", value: "07", change: "▼ can xu ly", up: false },
              ].map((m) => (
                <div key={m.label} className="metric-panel">
                  <span>{m.label}</span>
                  <strong>{m.value}</strong>
                  <span className={`change${m.up ? "" : " down"}`}>{m.change}</span>
                </div>
              ))}
            </div>
          </article>

          {/* Overview */}
          <article className="board-card hero-span">
            <div className="card-head">
              <h3>OVERVIEw — ket luan tu tat ca cac thong tin o duoi</h3>
              <span className="muted">Shortcut cho KH</span>
            </div>
            <div className="overview-band">
              <div className="overview-pill">Xu huong tang nhe — dong tien uu tien nhom chung khoan va bat dong san</div>
              <div className="overview-pill">Canh bao cat lo voi 3 tai khoan dat nguong — can xu ly truoc 14h</div>
              <div className="overview-pill">2 nganh dot bien trong phien sang: Chung khoan +12.4%, BDS +7.1%</div>
            </div>
          </article>

          {/* Gauge */}
          <article className="board-card">
            <div className="card-head">
              <h3>Xu huong thi truong</h3>
              <span className="muted">Tang / Giam?</span>
            </div>
            <div className="gauge-wrap">
              <div className="gauge-ring" />
              <div className="gauge-value">68%</div>
            </div>
            <div className="gauge-label" style={{ textAlign: "center", marginTop: 4 }}>Tich cuc — xu huong tang</div>
            <div className="text-lines" style={{ marginTop: 12 }}>
              <span /><span /><span /><span className="short" />
            </div>
          </article>

          {/* Money flow chart */}
          <article className="board-card wide">
            <div className="card-head">
              <h3>SS dong tien voi TB</h3>
              <span className="muted">12 phien gan nhat</span>
            </div>
            <div className="wave-chart" />
            <div className="chart-axis">
              {chartLabels.map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
            </div>
            <div className="chart-legend" style={{ marginTop: 8 }}>
              <div className="chart-legend-item"><span className="chart-legend-dot" /><span>Dong tien thuc</span></div>
              <div className="chart-legend-item"><span className="chart-legend-dot alt" /><span>Trung binh 20 phien</span></div>
            </div>
          </article>

          {/* Empty cards */}
          <article className="board-card">
            <div className="card-head"><h3>Nganh dot bien</h3></div>
            <div className="empty-stage">Nganh dot bien</div>
          </article>
          <article className="board-card">
            <div className="card-head"><h3>Dot bien cac co phieu</h3></div>
            <div className="empty-stage">Dot bien cac co phieu</div>
          </article>

          {/* Market allocation chart */}
          <article className="board-card hero-span">
            <div className="card-head">
              <h3>Dong tien tong thi truong phan bo vao cac nganh</h3>
              <span className="muted">Allocation theo phien</span>
            </div>
            <div className="wave-chart giant" />
            <div className="chart-axis">
              {chartLabels.map((label, index) => <span key={`${label}-${index}`}>{label}</span>)}
            </div>
            <div className="chart-legend" style={{ marginTop: 8 }}>
              <div className="chart-legend-item"><span className="chart-legend-dot" /><span>Tong dong tien vao</span></div>
              <div className="chart-legend-item"><span className="chart-legend-dot alt" /><span>Net flow</span></div>
            </div>
          </article>

          {/* Sector table */}
          <article className="board-card hero-span">
            <div className="card-head">
              <h3>Dong tien tong phan bo vao cac nganh</h3>
              <span className="muted">Bang tong hop</span>
            </div>
            <div className="table-shell">
              <div className="table-header">
                <span /><span /><span>Nganh</span>
                <span>Dong tien</span><span>Phan bo</span>
                <span>Thay doi</span><span>Trang thai</span>
              </div>
              {industryRows.map((row, i) => (
                <div key={row.name} className="table-row">
                  <span className="row-index">{String(i + 1).padStart(2, "0")}</span>
                  <span className="row-icon" />
                  <strong className="row-name">{row.name}</strong>
                  <span className="row-value">{row.value}</span>
                  <div className="row-bar-wrap">
                    <span className="row-bar" style={{ width: `${55 + i * 7}%` }} />
                  </div>
                  <span className={`row-change ${row.up ? "up" : "down"}`}>{row.change}</span>
                  <span className={`status-pill${row.up ? "" : " watch"}`}>{row.up ? "Tang" : "Theo doi"}</span>
                </div>
              ))}
              <div className="table-footer">
                <span>Hien thi 6 / 24 nganh</span>
                <div className="pagination">
                  {["1","2","3","›"].map((p, i) => (
                    <button key={p} className={`page-btn${i === 0 ? " active" : ""}`} type="button">{p}</button>
                  ))}
                </div>
              </div>
            </div>
          </article>

          {/* Watchlist */}
          <article className="board-card hero-span">
            <div className="card-head">
              <h3>Cac ma CK co dong tien vao manh theo nganh</h3>
              <span className="muted">Watchlist — Cap nhat theo phien</span>
            </div>
            <div className="watchlist-shell">
              {tickerRows.map((row) => (
                <div key={row.ticker} className="watchlist-item">
                  <div className="watchlist-ticker">{row.ticker}</div>
                  <div className="watchlist-info">
                    <strong>{row.name}</strong>
                    <p>{row.desc}</p>
                  </div>
                  <span className="pill up">RS {row.rs}</span>
                </div>
              ))}
            </div>
          </article>

        </section>
      </section>
    </main>
  );
}
