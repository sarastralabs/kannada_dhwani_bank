/**
 * Generate frontend/.dev-certs/*.pem with localhost + LAN IP in SAN.
 * Usage: node scripts/generate-dev-cert.mjs [192.168.1.22]
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import selfsigned from "selfsigned";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");
const certDir = path.join(frontendRoot, ".dev-certs");
const ip = (process.argv[2] || "127.0.0.1").trim();

fs.mkdirSync(certDir, { recursive: true });

const altNames = [
  { type: 2, value: "localhost" },
  { type: 7, ip: "127.0.0.1" },
];
if (ip && ip !== "127.0.0.1") {
  altNames.push({ type: 7, ip });
}

const pems = await selfsigned.generate([{ name: "commonName", value: "localhost" }], {
  days: 825,
  keySize: 2048,
  algorithm: "sha256",
  extensions: [
    {
      name: "basicConstraints",
      cA: false,
    },
    {
      name: "keyUsage",
      digitalSignature: true,
      keyEncipherment: true,
    },
    {
      name: "extKeyUsage",
      serverAuth: true,
    },
    {
      name: "subjectAltName",
      altNames,
    },
  ],
});

fs.writeFileSync(path.join(certDir, "key.pem"), pems.private, "utf8");
fs.writeFileSync(path.join(certDir, "cert.pem"), pems.cert, "utf8");

console.log(`Wrote ${certDir}`);
console.log(`SAN: localhost, 127.0.0.1${ip !== "127.0.0.1" ? `, ${ip}` : ""}`);
