import { copyFile, mkdir } from "node:fs/promises";

// Run only for web deployment, after Vite builds the website. Keeping the APK
// outside public/ prevents packaging a copy of it inside later Android builds.
await mkdir(new URL("../dist/downloads/", import.meta.url), { recursive: true });
await copyFile(
  new URL("../release-artifacts/EcoRefill.apk", import.meta.url),
  new URL("../dist/downloads/EcoRefill.apk", import.meta.url)
);
console.log("Android APK published at /downloads/EcoRefill.apk");
