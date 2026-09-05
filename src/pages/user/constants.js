import { History, Home, QrCode, ShoppingBag, User } from "lucide-react";

export const POINT_PACKAGES = [
  {
    id: 1,
    name: "Starter Pack",
    points: 100,
    price: 20,
    description: "Good for small refills",
  },
  {
    id: 2,
    name: "Eco Saver Pack",
    points: 250,
    price: 45,
    description: "Best for regular users",
  },
  {
    id: 3,
    name: "Green Hero Pack",
    points: 500,
    price: 85,
    description: "More points, better value",
  },
  {
    id: 4,
    name: "Eco Champion Pack",
    points: 1000,
    price: 160,
    description: "Recommended for frequent users",
  },
];

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
