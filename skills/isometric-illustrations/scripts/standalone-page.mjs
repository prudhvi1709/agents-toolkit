import { createHash } from "node:crypto";
import { pageHtml } from "../kit/iso-kit.mjs";

const hashOf = (source) => `'sha256-${createHash("sha256").update(source).digest("base64")}'`;

// This targets the kit's trusted generated markup, not arbitrary HTML parsing.
// If its page template changes, use an HTML parser or external CSS/modules.
export function standalonePageHtml(options) {
  const html = pageHtml(options);
  const scriptPattern = /<script type="module">([\s\S]*?)<\/script>/g;
  const scripts = [...html.matchAll(scriptPattern)].map((match) => hashOf(match[1]));
  const markup = html.replace(scriptPattern, "");
  const styles = [...markup.matchAll(/<style>([\s\S]*?)<\/style>/g)].map((match) => hashOf(match[1]));
  const attributes = [...markup.matchAll(/\sstyle="([^"]*)"/g)].map((match) => {
    const value = match[1].replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
    return hashOf(value);
  });
  const policy = [
    "default-src 'none'",
    `script-src ${scripts.length ? scripts.join(" ") : "'none'"}`,
    `style-src ${[...new Set([...styles, ...attributes])].join(" ")}${attributes.length ? " 'unsafe-hashes'" : ""}`,
    "img-src data: blob:",
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'none'",
  ].join("; ");
  return html.replace('<meta charset="utf-8">', `<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="${policy}">`);
}
