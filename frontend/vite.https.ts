import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type { ServerOptions as HttpsServerOptions } from "node:https";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Laptop-only dev without cert warnings — mic/camera OK on http://127.0.0.1 */
export function devUseHttp(): boolean {
  return process.env.VITE_DEV_HTTP === "1";
}

/** Dev cert with LAN IP in SAN — run scripts/setup-dev-https.ps1 */
export function loadDevHttps(): HttpsServerOptions | undefined {
  if (devUseHttp()) {
    return undefined;
  }
  const certDir = path.resolve(__dirname, ".dev-certs");
  const certPath = path.join(certDir, "cert.pem");
  const keyPath = path.join(certDir, "key.pem");
  if (!fs.existsSync(certPath) || !fs.existsSync(keyPath)) {
    return undefined;
  }
  return {
    key: fs.readFileSync(keyPath),
    cert: fs.readFileSync(certPath),
  };
}

export function useBasicSslFallback(): boolean {
  return !devUseHttp() && loadDevHttps() === undefined;
}
