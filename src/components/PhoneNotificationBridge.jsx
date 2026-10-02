import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { auth } from "../firebase/firebase";
import { hasPendingNotification, pendingNotificationPath, startPhoneNotifications, subscribeNotificationTaps } from "../firebase/phoneNotifications";

export default function PhoneNotificationBridge() {
  const navigate = useNavigate();
  useEffect(() => {
    const openAlert = () => {
      if (!hasPendingNotification()) return;
      const path = pendingNotificationPath(auth.currentUser?.uid);
      if (path) navigate(path);
      else if (!auth.currentUser) navigate("/login", { replace: true });
    };
    const unsubscribe = subscribeNotificationTaps(openAlert);
    startPhoneNotifications().catch(() => {});
    openAlert();
    return unsubscribe;
  }, [navigate]);
  return null;
}
