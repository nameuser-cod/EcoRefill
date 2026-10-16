import { mkdir, writeFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QRCodeSVG } from "qrcode.react";
import { INSTALL_PAGE_URL } from "../src/config/appLinks.js";

const directory = new URL("../public/downloads/", import.meta.url);
await mkdir(directory, { recursive: true });
const svg = renderToStaticMarkup(createElement(QRCodeSVG, {
  xmlns: "http://www.w3.org/2000/svg",
  value: INSTALL_PAGE_URL,
  size: 1024,
  level: "M",
  marginSize: 4,
  title: "Scan to explore and install EcoRefill",
}));
await writeFile(new URL("EcoRefill-landing-qr.svg", directory), svg + "\n");
console.log(`Installation QR points to ${INSTALL_PAGE_URL}`);
