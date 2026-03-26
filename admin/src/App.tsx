import { Refine, Authenticated, useLogout } from "@refinedev/core";
import { RefineThemes } from "@refinedev/antd";
import "@refinedev/antd/dist/reset.css";
import {
  BarChartOutlined,
  BulbOutlined,
  DatabaseOutlined,
  DashboardOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  LogoutOutlined,
  MenuOutlined,
  MoonOutlined,
  SafetyCertificateOutlined,
  SettingOutlined,
  StockOutlined,
  SyncOutlined,
  TeamOutlined,
  LineChartOutlined,
} from "@ant-design/icons";
import { Button, ConfigProvider, Drawer, Grid, Menu, Switch, Typography, theme as antdTheme } from "antd";
import type { MenuProps } from "antd";
import { useMemo, useState } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import "./index.css";
import { dataProvider } from "./providers/data-provider";
import { authProvider } from "./providers/auth-provider";
import { LoginPage } from "./pages/login";
import { AnalyticsPage } from "./pages/analytics";
import { DashboardPage } from "./pages/dashboard";
import { CategoriesPage } from "./pages/categories";
import { PostsPage } from "./pages/posts";
import { SettingsPage } from "./pages/settings";
import { SyncDataPage } from "./pages/sync-data";
import { StocksPage } from "./pages/stocks";
import { RolesPage } from "./pages/roles";
import { UsersPage } from "./pages/users";
import { StockFinanceChartsPage } from "./pages/stock-finance-charts";
import { StockFinanceChartDetailPage } from "./pages/stock-finance-chart-detail";
import { T0DataPage } from "./pages/t0-data";
import { ForeignTradingPage } from "./pages/foreign-trading";

const THEME_STORAGE_KEY = "admin_theme_mode";

function AdminMenu({ onNavigate }: { onNavigate?: () => void }) {
  const location = useLocation();
  const items: MenuProps["items"] = [
    {
      type: "group",
      label: "Overview",
      children: [
        { key: "/dashboard", icon: <DashboardOutlined />, label: <Link to="/dashboard">Dashboard</Link> },
      ],
    },
    {
      type: "group",
      label: "Content",
      children: [
        { key: "/posts", icon: <FileTextOutlined />, label: <Link to="/posts">Posts</Link> },
        { key: "/categories", icon: <FolderOpenOutlined />, label: <Link to="/categories">Categories</Link> },
      ],
    },
    {
      type: "group",
      label: "Data",
      children: [
        { key: "/stocks", icon: <StockOutlined />, label: <Link to="/stocks">Stocks</Link> },
        { key: "/foreign-trading", icon: <LineChartOutlined />, label: <Link to="/foreign-trading">GD nuoc ngoai</Link> },
        { key: "/t0-data", icon: <LineChartOutlined />, label: <Link to="/t0-data">Du lieu T0</Link> },
        { key: "/stock-finance-charts", icon: <LineChartOutlined />, label: <Link to="/stock-finance-charts">Finance Charts</Link> },
        { key: "/sync-data", icon: <SyncOutlined />, label: <Link to="/sync-data">Sync du lieu</Link> },
        { key: "/analytics", icon: <BarChartOutlined />, label: <Link to="/analytics">Tong hop so lieu</Link> },
      ],
    },
    {
      type: "group",
      label: "System",
      children: [
        { key: "/settings", icon: <SettingOutlined />, label: <Link to="/settings">Settings</Link> },
        { key: "/users", icon: <TeamOutlined />, label: <Link to="/users">Users</Link> },
        { key: "/roles", icon: <SafetyCertificateOutlined />, label: <Link to="/roles">Roles</Link> },
      ],
    },
  ];

  const menuKeys = [
    "/dashboard",
    "/settings",
    "/analytics",
    "/sync-data",
    "/categories",
    "/posts",
    "/stocks",
    "/foreign-trading",
    "/t0-data",
    "/stock-finance-charts",
    "/users",
    "/roles",
  ];
  const selectedKey =
    menuKeys.find((key) => location.pathname === key || location.pathname.startsWith(`${key}/`)) ?? "/dashboard";

  return (
    <Menu
      className="admin-menu"
      mode="inline"
      selectedKeys={[selectedKey]}
      items={items}
      onClick={onNavigate}
      style={{ width: "100%", border: "none" }}
    />
  );
}

function ProtectedLayout({ isDark, onToggleTheme }: { isDark: boolean; onToggleTheme: (checked: boolean) => void }) {
  const { mutate: logout } = useLogout();
  const location = useLocation();
  const screens = Grid.useBreakpoint();
  const isMobile = !screens.lg;
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const titleByPath: Record<string, string> = {
    "/dashboard": "Dashboard",
    "/posts": "Post Management",
    "/categories": "Category Management",
    "/stocks": "Stock Symbols",
    "/foreign-trading": "Foreign Trading",
    "/t0-data": "T0 Data",
    "/stock-finance-charts": "Vietstock Finance Charts",
    "/sync-data": "Data Synchronization",
    "/analytics": "Analytics",
    "/settings": "Settings",
    "/users": "User Management",
    "/roles": "Role & Permission Management",
  };
  const activePath = Object.keys(titleByPath).find((path) => location.pathname.startsWith(path)) ?? "/dashboard";
  const activeTitle = titleByPath[activePath];

  return (
    <div className={`admin-shell ${isDark ? "admin-shell-dark" : ""}`}>
      {!isMobile ? <aside className="admin-sidebar">
        <div className="admin-brand">
          <DatabaseOutlined />
          <div>
            <Typography.Text strong style={{ color: "#fff", display: "block" }}>
              Stock Admin
            </Typography.Text>
            <Typography.Text style={{ color: "rgba(255,255,255,0.65)", fontSize: 12 }}>
              Operations Console
            </Typography.Text>
          </div>
        </div>
        <AdminMenu />
        <div className="admin-sidebar-footer">
          <Button
            icon={<LogoutOutlined />}
            onClick={() => logout()}
            className="admin-logout-btn"
            block
          >
            Logout
          </Button>
        </div>
      </aside> : null}

      <Drawer
        className={`admin-mobile-drawer ${isDark ? "admin-mobile-drawer-dark" : ""}`}
        placement="left"
        open={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
        closable={false}
        width={300}
        styles={{ body: { padding: 0 } }}
      >
        <aside className="admin-sidebar admin-sidebar-mobile">
          <div className="admin-brand">
            <DatabaseOutlined />
            <div>
              <Typography.Text strong style={{ color: "#fff", display: "block" }}>
                Stock Admin
              </Typography.Text>
              <Typography.Text style={{ color: "rgba(255,255,255,0.65)", fontSize: 12 }}>
                Operations Console
              </Typography.Text>
            </div>
          </div>
          <AdminMenu onNavigate={() => setMobileMenuOpen(false)} />
          <div className="admin-sidebar-footer">
            <Button
              icon={<LogoutOutlined />}
              onClick={() => logout()}
              className="admin-logout-btn"
              block
            >
              Logout
            </Button>
          </div>
        </aside>
      </Drawer>

      <main className="admin-main">
        <header className="admin-topbar">
          <div className="admin-topbar-main">
            {isMobile ? (
              <Button
                type="text"
                icon={<MenuOutlined />}
                className="admin-mobile-menu-btn"
                onClick={() => setMobileMenuOpen(true)}
                aria-label="Open navigation menu"
              />
            ) : null}
            <div>
              <Typography.Title level={4} style={{ margin: 0 }}>
                {activeTitle}
              </Typography.Title>
              <Typography.Text type="secondary">Manage resources, permissions, and data flow</Typography.Text>
            </div>
          </div>
          <div className="admin-topbar-actions">
            <div className="admin-theme-toggle">
              <MoonOutlined />
              <Switch
                size="small"
                checked={isDark}
                onChange={onToggleTheme}
                checkedChildren={<BulbOutlined />}
                unCheckedChildren={<BulbOutlined />}
              />
            </div>
          </div>
        </header>
        <section className="admin-content">
          <Outlet />
        </section>
      </main>
    </div>
  );
}

function App() {
  const [isDark, setIsDark] = useState(() => {
    const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
    if (storedTheme === "dark") {
      return true;
    }
    if (storedTheme === "light") {
      return false;
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  });

  const configTheme = useMemo(
    () => ({
      ...RefineThemes.Blue,
      algorithm: isDark ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
    }),
    [isDark],
  );

  const handleToggleTheme = (checked: boolean) => {
    setIsDark(checked);
    localStorage.setItem(THEME_STORAGE_KEY, checked ? "dark" : "light");
  };

  return (
    <BrowserRouter>
      <ConfigProvider theme={configTheme}>
        <Refine
          dataProvider={dataProvider}
          authProvider={authProvider}
          resources={[
            { name: "settings", list: "/settings" },
            { name: "dashboard", list: "/dashboard" },
            { name: "analytics", list: "/analytics" },
            { name: "sync-data", list: "/sync-data" },
            { name: "categories", list: "/categories" },
            { name: "posts", list: "/posts" },
            { name: "stocks", list: "/stocks" },
            { name: "foreign-trading", list: "/foreign-trading" },
            { name: "t0-data", list: "/t0-data" },
            { name: "stock-finance-charts", list: "/stock-finance-charts" },
            { name: "users", list: "/users" },
            { name: "roles", list: "/roles" },
          ]}
        >
          <Routes>
            <Route path="/login" element={<LoginPage isDark={isDark} onToggleTheme={handleToggleTheme} />} />
            <Route
              element={
                <Authenticated key="auth-routes" fallback={<Navigate to="/login" replace />}>
                  <ProtectedLayout isDark={isDark} onToggleTheme={handleToggleTheme} />
                </Authenticated>
              }
            >
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/sync-data" element={<SyncDataPage />} />
              <Route path="/categories" element={<CategoriesPage />} />
              <Route path="/posts" element={<PostsPage />} />
              <Route path="/stocks" element={<StocksPage />} />
              <Route path="/foreign-trading" element={<ForeignTradingPage />} />
              <Route path="/t0-data" element={<T0DataPage />} />
              <Route path="/stock-finance-charts" element={<StockFinanceChartsPage />} />
              <Route path="/stock-finance-charts/:ticker" element={<StockFinanceChartDetailPage />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/roles" element={<RolesPage />} />
            </Route>
          </Routes>
        </Refine>
      </ConfigProvider>
    </BrowserRouter>
  );
}

export default App;
