import Link from "next/link";
import { pricingPlans, publicNav, sitemapGroups, solutionCards } from "@/lib/portal-data";

export default function HomePage() {
  return (
    <main className="public-shell">
      <aside className="left-rail public-rail">
        <div className="brand-block">
          <span className="eyebrow">Public</span>
          <h1>Trading Platform</h1>
          <p>Nen tang quan ly va tu van chung khoan tach ro Public va Workspace.</p>
        </div>
        <nav className="nav-tree">
          {publicNav.map((item) => (
            <Link key={item.label} href={item.href ?? "#"} className="nav-item">
              <span>{item.label}</span>
              {item.badge ? <small>{item.badge}</small> : null}
            </Link>
          ))}
        </nav>
        <div className="rail-panel">
          <p className="panel-label">Sitemap</p>
          {sitemapGroups.map((group) => (
            <div key={group.title} className="mini-tree">
              <strong>{group.title}</strong>
              <p>{group.description}</p>
            </div>
          ))}
        </div>
      </aside>

      <div className="public-content">
        <header className="hero-card">
          <div>
            <span className="eyebrow">Public area</span>
            <h2>Ban trang chu mang phong cach dashboard, nhin la thay ngay gia tri san pham</h2>
            <p>
              Giao dien duoc dung theo mockup: hero ro thong diep, khoi giai phap,
              bang gia va duong dan vao workspace sau dang nhap.
            </p>
            <div className="action-row">
              <Link href="/register" className="primary-button">
                Bat dau ngay
              </Link>
              <Link href="/login" className="ghost-button">
                Dang nhap workspace
              </Link>
            </div>
          </div>
          <div className="hero-metrics">
            <div className="metric-card">
              <span>Assets theo doi</span>
              <strong>1.248 ma</strong>
            </div>
            <div className="metric-card">
              <span>Khach hang moi</span>
              <strong>+86 / thang</strong>
            </div>
            <div className="metric-card">
              <span>Alert xu huong</span>
              <strong>Realtime</strong>
            </div>
          </div>
        </header>

        <section id="giai-phap" className="content-card">
          <div className="section-heading">
            <span className="eyebrow">Giai phap</span>
            <h3>Tu marketing ben ngoai den bo cong cu lam viec ben trong</h3>
          </div>
          <div className="card-grid three">
            {solutionCards.map((card) => (
              <article key={card.title} className="feature-card">
                <div className="icon-dot" />
                <h4>{card.title}</h4>
                <p>{card.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="showcase-grid">
          <article className="content-card">
            <div className="section-heading">
              <span className="eyebrow">Workspace preview</span>
              <h3>Cac chi so va assets</h3>
            </div>
            <div className="chart-hero">
              <div className="stat-bar" />
              <div className="wave-chart large" />
            </div>
          </article>
          <article className="content-card">
            <div className="section-heading">
              <span className="eyebrow">Overview</span>
              <h3>Ket luan nhanh tu du lieu phia duoi</h3>
            </div>
            <div className="summary-grid">
              <div className="summary-box">Xu huong thi truong</div>
              <div className="summary-box">SS dong tien voi TB</div>
              <div className="summary-box">Nganh dot bien</div>
              <div className="summary-box">Dot bien co phieu</div>
            </div>
          </article>
        </section>

        <section id="bang-gia" className="content-card">
          <div className="section-heading">
            <span className="eyebrow">Bang gia</span>
            <h3>3 goi dich vu theo dung sitemap ban gui</h3>
          </div>
          <div className="card-grid three">
            {pricingPlans.map((plan) => (
              <article key={plan.name} className="price-card">
                <div>
                  <h4>{plan.name}</h4>
                  <strong>{plan.price}</strong>
                </div>
                <p>{plan.detail}</p>
                <ul className="flat-list">
                  {plan.features.map((feature) => (
                    <li key={feature}>{feature}</li>
                  ))}
                </ul>
              </article>
            ))}
          </div>
        </section>

        <section id="ve-chung-toi" className="content-card about-card">
          <div>
            <span className="eyebrow">Ve chung toi</span>
            <h3>Xay nen tang de MG/CTV co the ban hang, phan tich va cham khach hang tren cung mot bo giao dien</h3>
          </div>
          <div className="action-row">
            <Link href="/workspace" className="primary-button">
              Xem workspace
            </Link>
            <Link href="/forgot-password" className="ghost-button">
              Quen mat khau
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
