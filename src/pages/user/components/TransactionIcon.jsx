import { Droplets, History, Recycle, ShoppingBag } from "lucide-react";

function TransactionIcon({ size = 22, type }) {
  if (type === "recycling") return <Recycle size={size} />;
  if (type === "water_refill") return <Droplets size={size} />;
  if (type === "point_purchase") return <ShoppingBag size={size} />;

  return <History size={size} />;
}

export default TransactionIcon;
