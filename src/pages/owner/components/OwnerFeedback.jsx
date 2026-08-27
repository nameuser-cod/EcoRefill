import { AlertTriangle, LoaderCircle } from "lucide-react";

export function OwnerLoading({ label = "Loading your workspace..." }) {
  return (
    <div className="owner-app-state owner-app-loading" role="status">
      <LoaderCircle className="owner-app-spin" size={28} />
      <p>{label}</p>
    </div>
  );
}

export function OwnerError({ message }) {
  if (!message) return null;

  return (
    <div className="owner-app-message owner-app-message-error" role="alert">
      <AlertTriangle size={20} />
      <p>{message}</p>
    </div>
  );
}

export function OwnerEmpty({ icon: Icon, title, description }) {
  return (
    <div className="owner-app-empty">
      {Icon && <Icon size={25} />}
      <strong>{title}</strong>
      <p>{description}</p>
    </div>
  );
}
