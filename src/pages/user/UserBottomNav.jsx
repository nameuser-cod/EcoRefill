import { History, Home, QrCode, ShoppingBag, User } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

const NAV_ITEMS = [
  {
    label: "Home",
    path: "/user/dashboard",
    icon: Home,
  },
  {
    label: "Scan",
    path: "/user/scan-qr",
    icon: QrCode,
  },
  {
    label: "Points",
    path: "/user/buy-points",
    icon: ShoppingBag,
  },
  {
    label: "History",
    path: "/user/history",
    icon: History,
  },
  {
    label: "Profile",
    path: "/user/profile",
    icon: User,
  },
];

function UserBottomNav() {
  const navigate = useNavigate();
  const location = useLocation();

  const isActive = (path) => {
    if (path === "/user/dashboard") {
      return location.pathname === path;
    }

    if (path === "/user/scan-qr") {
      return (
        location.pathname.startsWith("/user/scan-qr") ||
        location.pathname.startsWith("/user/camera-scan")
      );
    }

    return location.pathname.startsWith(path);
  };

  return (
    <nav className="user-bottom-nav" aria-label="User navigation">
      {NAV_ITEMS.map(({ label, path, icon: Icon }) => {
        const active = isActive(path);

        return (
          <button
            type="button"
            key={path}
            className={`user-bottom-nav-item${active ? " active" : ""}`}
            onClick={() => navigate(path)}
            aria-label={label}
            aria-current={active ? "page" : undefined}
          >
            <Icon size={21} />
            <span>{label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default UserBottomNav;
