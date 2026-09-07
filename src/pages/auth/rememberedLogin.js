const REMEMBERED_EMAIL_KEY = "ecorefill.rememberedEmail";

export function readRememberedEmail() {
  try {
    return localStorage.getItem(REMEMBERED_EMAIL_KEY) || "";
  } catch {
    return "";
  }
}

export function saveRememberedEmail(email) {
  try {
    if (email) {
      localStorage.setItem(REMEMBERED_EMAIL_KEY, email.trim().toLowerCase());
    } else {
      localStorage.removeItem(REMEMBERED_EMAIL_KEY);
    }
  } catch {
    // Unavailable preference storage must not interrupt an authenticated login.
  }
}
