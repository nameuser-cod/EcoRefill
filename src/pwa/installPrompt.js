const displayMode = window.matchMedia("(display-mode: standalone)");
let snapshot = { prompt: null, installed: displayMode.matches || navigator.standalone === true };
const listeners = new Set();

function update(changes) {
  snapshot = { ...snapshot, ...changes };
  listeners.forEach((listener) => listener());
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  update({ prompt: event });
});
window.addEventListener("appinstalled", () => update({ prompt: null, installed: true }));
displayMode.addEventListener("change", (event) => update({ installed: event.matches || navigator.standalone === true }));

export const getInstallSnapshot = () => snapshot;
export function subscribeToInstall(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export async function promptInstall() {
  const prompt = snapshot.prompt;
  if (!prompt) return;
  try {
    await prompt.prompt();
    await prompt.userChoice;
  } finally {
    update({ prompt: null });
  }
}
