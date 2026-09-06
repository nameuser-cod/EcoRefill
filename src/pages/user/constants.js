import { History, Home, QrCode, ShoppingBag, User } from "lucide-react";

export const WATER_OPTIONS = [
  { waterAmountMl: 250, pointsRequired: 3, label: "Small" },
  { waterAmountMl: 500, pointsRequired: 5, label: "Medium" },
  { waterAmountMl: 1000, pointsRequired: 10, label: "Large" },
];

export const USER_NAV_ITEMS = [
  { label: "Home", path: "/user/dashboard", icon: Home },
  { label: "Scan", path: "/user/scan-qr", icon: QrCode },
  { label: "Points", path: "/user/buy-points", icon: ShoppingBag },
  { label: "History", path: "/user/history", icon: History },
  { label: "Profile", path: "/user/profile", icon: User },
];
