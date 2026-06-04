// Generates the 1200×630 Open Graph / Twitter social card at public/og-image.png.
// On-brand: Carbon gray-100 surface, IBM-blue accent, white type.
// Run: node scripts/gen_og.mjs
import sharp from "sharp";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const out = resolve(__dirname, "../public/og-image.png");

const W = 1200;
const H = 630;
const BLUE = "#0f62fe";

// The CLDK "layers" mark (viewBox 0 0 20 20), placed top-left and tinted blue.
const layers = `
  <g transform="translate(96 92) scale(2.4)" fill="${BLUE}">
    <path d="M0.5,6.9L0.5,6.9l9,5l0,0C9.7,12,9.8,12,10,12s0.3,0,0.5-0.1l0,0l9-5l0,0C19.8,6.7,20,6.4,20,6c0-0.4-0.2-0.7-0.5-0.9l0,0l-9-5l0,0C10.3,0,10.2,0,10,0S9.7,0,9.5,0.1l0,0l-9,5l0,0C0.2,5.3,0,5.6,0,6C0,6.4,0.2,6.7,0.5,6.9z"/>
    <path d="M19,9c-0.2,0-0.3,0-0.5,0.1l0,0L10,13.9L1.5,9.1l0,0C1.3,9,1.2,9,1,9c-0.6,0-1,0.4-1,1c0,0.4,0.2,0.7,0.5,0.9l0,0l9,5l0,0C9.7,16,9.8,16,10,16s0.3,0,0.5-0.1l0,0l9-5l0,0c0.3-0.2,0.5-0.5,0.5-0.9C20,9.4,19.6,9,19,9z"/>
    <path d="M19,13c-0.2,0-0.3,0-0.5,0.1l0,0L10,17.9l-8.5-4.7l0,0C1.3,13,1.2,13,1,13c-0.6,0-1,0.4-1,1c0,0.4,0.2,0.7,0.5,0.9l0,0l9,5l0,0C9.7,20,9.8,20,10,20s0.3,0,0.5-0.1l0,0l9-5l0,0c0.3-0.2,0.5-0.5,0.5-0.9C20,13.4,19.6,13,19,13z"/>
  </g>`;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">
  <rect width="${W}" height="${H}" fill="#161616"/>
  <rect x="0" y="0" width="${W}" height="8" fill="${BLUE}"/>
  ${layers}
  <text x="150" y="120" font-family="Helvetica, Arial, sans-serif" font-size="34" font-weight="700" fill="#c6c6c6" letter-spacing="2">CODELLM-DEVKIT</text>
  <text x="96" y="280" font-family="Helvetica, Arial, sans-serif" font-size="118" font-weight="800" fill="#ffffff">CLDK</text>
  <text x="98" y="360" font-family="Helvetica, Arial, sans-serif" font-size="40" font-weight="600" fill="#a6c8ff">One analysis interface over every language.</text>
  <text x="98" y="420" font-family="Helvetica, Arial, sans-serif" font-size="34" font-weight="400" fill="#8d8d8d">Call graphs, symbol tables, and reachability,</text>
  <text x="98" y="466" font-family="Helvetica, Arial, sans-serif" font-size="34" font-weight="400" fill="#8d8d8d">program analysis your agents can call.</text>
  <text x="96" y="566" font-family="Helvetica, Arial, sans-serif" font-size="30" font-weight="700" fill="${BLUE}">codellm-devkit.info</text>
</svg>`;

await sharp(Buffer.from(svg)).png().toFile(out);
console.log("wrote", out);
