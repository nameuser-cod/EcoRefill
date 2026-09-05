import { useLocation, useNavigate } from "react-router-dom";
import { USER_NAV_ITEMS } from "../constants";

const isPathActive = (currentPath, itemPath) => {
  if (itemPath === "/user/dashboard") return currentPath === itemPath;

  if (itemPath === "/user/scan-qr") {
    return (
      currentPath.startsWith("/user/scan-qr") ||
      currentPath.startsWith("/user/camera-scan")
    );
  }

  return currentPath.startsWith(itemPath);
};

function UserBottomNav() {
  const navigate = useNavigate();
  const { pathname } = useLocation();

  return (
    <nav className="user-bottom-nav" aria-label="User navigation">
      {USER_NAV_ITEMS.map(({ label, path, icon: Icon }) => {
        const active = isPathActive(pathname, path);

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
