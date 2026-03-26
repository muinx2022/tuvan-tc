export type NavItem = {
  label: string;
  href?: string;
  badge?: string;
  icon?: string;
  children?: NavItem[];
};

export const publicNav: NavItem[] = [
  { label: "Trang chu", href: "/" },
  { label: "Giai phap", href: "/#giai-phap" },
  { label: "Bang gia", href: "/#bang-gia" },
  { label: "Ve chung toi", href: "/#ve-chung-toi" },
  { label: "Dang nhap", href: "/login", badge: "Auth" },
];

export const workspaceNav: NavItem[] = [
  {
    label: "Dashboard",
    href: "/workspace",
    icon: "📊",
    children: [
      { label: "Chi so thi truong thoi gian thuc (VNI, VN30...)" },
      { label: "Thong ke nhanh (Tong KH, AUM, KH moi)" },
      { label: "Canh bao & Nhac viec", badge: "7" },
    ],
  },
  {
    label: "Trung tam Phan tich",
    icon: "📝",
    children: [
      {
        label: "Nhip dap thi truong",
        icon: "🌐",
        children: [
          { label: "Overview ket luan shortcut cho KH" },
          { label: "Bieu do Trend & Dong tien trung binh" },
        ],
      },
      {
        label: "Bo loc co phieu (Screener)",
        icon: "🔍",
        children: [
          { label: "Loc ma dot bien toan thi truong (KL, Gia)" },
          { label: "Loc ma dot bien theo nhom nganh" },
        ],
      },
      {
        label: "Phan tich Nganh",
        icon: "📈",
        children: [
          { label: "Dong tien phan bo vao cac nganh" },
          { label: "Danh sach ma nganh kem chi so RS" },
        ],
      },
      {
        label: "Danh muc theo doi (Watchlist)",
        icon: "⭐",
      },
    ],
  },
  {
    label: "Quan ly Khach hang",
    icon: "👥",
    children: [
      {
        label: "Danh sach Khach hang",
        icon: "📋",
        children: [
          { label: "Loc theo The/Tags (Tiem nang, VIP...)" },
        ],
      },
      {
        label: "Ho so chi tiet KH (Client Profile)",
        icon: "👤",
        children: [
          { label: "Thong tin ca nhan & Goi dich vu dang dung" },
          { label: "Lich su tuong tac (Nhat ky tu van, goi dien)" },
          { label: "Danh muc mo phong (Theo doi lai/lo)" },
        ],
      },
      {
        label: "Quan ly Doi nhom",
        icon: "👥",
        children: [
          { label: "Xem hieu suat CTV (danh cho MG cap quan ly)" },
        ],
      },
    ],
  },
  {
    label: "Tai khoan & Cai dat",
    icon: "⚙️",
    children: [
      { label: "Thong tin ca nhan & Doi mat khau", icon: "👤" },
      { label: "Quan ly Goi dich vu (Gia han, Lich su thanh toan)", icon: "💳" },
      { label: "Tuy bien giao dien (Widget, Sang/Toi)", icon: "🎨" },
    ],
  },
];

export const sitemapGroups = [
  {
    title: "Khu vuc Public",
    description: "Trang ngoai cho marketing, gioi thieu gia tri va ban goi.",
    items: [
      "Trang chu voi banner va USP",
      "Giai phap CRM va cong cu dong tien",
      "Bang gia cho 3 goi dich vu",
      "Ve chung toi, lien he, chinh sach",
      "Dang nhap / Dang ky",
    ],
  },
  {
    title: "Khu vuc Workspace",
    description: "Ban lam viec sau dang nhap cho MG/CTV.",
    items: [
      "Dashboard tong quan va canh bao",
      "Trung tam phan tich dong tien",
      "CRM quan ly khach hang",
      "Tai khoan va cai dat",
    ],
  },
];

export const solutionCards = [
  {
    title: "Nhip dap thi truong",
    text: "Tong hop chi so, xu huong, do manh dong tien va thong diep hanh dong trong mot man hinh.",
  },
  {
    title: "CRM cho moi moi gioi",
    text: "Quan ly khach hang, lich su tu van, tags, nhac viec va hieu suat doi nhom.",
  },
  {
    title: "Bo loc dot bien",
    text: "Tim co phieu va nhom nganh co gia, khoi luong, dong tien bat thuong de ra quyet dinh nhanh.",
  },
];

export const pricingPlans = [
  {
    name: "Goi 1",
    price: "790K",
    detail: "Phu hop CTV can dashboard va bo loc co ban.",
    features: ["Dashboard tong quan", "Screener co phieu", "Watchlist ca nhan"],
  },
  {
    name: "Goi 2",
    price: "1.590K",
    detail: "Phu hop moi gioi can CRM va phan tich nganh.",
    features: ["Tat ca Goi 1", "CRM khach hang", "Phan tich nganh va dong tien"],
  },
  {
    name: "Goi 3",
    price: "Lien he",
    detail: "Danh cho team lead can quan ly doi nhom va tuy bien sau hon.",
    features: ["Tat ca Goi 2", "Quan ly doi nhom", "Bao cao nang cao"],
  },
];
