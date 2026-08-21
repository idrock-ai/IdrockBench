#!/usr/bin/env node
// Build step for the static site.
//
// Copies the deployable assets into dist/ and appends a content hash to local
// asset references, so a CDN or browser cannot serve a stale copy. Source
// files are never modified.
//
// results.json is fingerprinted too, and the fetch in script.js is rewritten to
// match. It carries every published number, so it is the one file that must
// never be stale — and the reference that matters is the fetch, not a link.

const fs = require("fs");
const crypto = require("crypto");
const path = require("path");

const ROOT = __dirname;
const DIST = path.join(ROOT, "dist");

// Build tooling and docs, never shipped.
const EXCLUDE = new Set([
    "build.js", "package.json", "package-lock.json", "README.md",
    "supabase-setup.sql",
]);
const ASSET_EXTS = new Set([
    ".html", ".css", ".js", ".json", ".png", ".jpg", ".jpeg", ".svg", ".ico",
    ".webp", ".gif", ".woff", ".woff2", ".ttf", ".txt", ".xml", ".webmanifest",
]);

// Assets fingerprinted in HTML. Add here when splitting a file.
const HASHED = ["styles.css", "script.js", "submit.js", "results.json"];

function hashFile(file) {
    return crypto.createHash("sha256")
        .update(fs.readFileSync(path.join(ROOT, file)))
        .digest("hex").slice(0, 10);
}

fs.rmSync(DIST, { recursive: true, force: true });
fs.mkdirSync(DIST, { recursive: true });

for (const name of fs.readdirSync(ROOT)) {
    if (EXCLUDE.has(name)) continue;
    const src = path.join(ROOT, name);
    if (!fs.statSync(src).isFile()) continue;
    if (!ASSET_EXTS.has(path.extname(name).toLowerCase())) continue;
    fs.copyFileSync(src, path.join(DIST, name));
}

const hashes = Object.fromEntries(HASHED.map((a) => [a, hashFile(a)]));

// Rewrite only href/src attribute values. Matching the bare filename anywhere
// in the document also rewrites link text and comments, which is how a stale
// build hash ended up committed back into the source HTML.
for (const page of fs.readdirSync(DIST).filter((f) => f.endsWith(".html"))) {
    const file = path.join(DIST, page);
    let html = fs.readFileSync(file, "utf8");
    for (const [asset, hash] of Object.entries(hashes)) {
        const pattern = new RegExp(
            `((?:href|src)=")(${asset.replace(".", "\\.")})(\\?v=[a-f0-9]+)?(")`, "g",
        );
        html = html.replace(pattern, `$1${asset}?v=${hash}$4`);
    }
    fs.writeFileSync(file, html);
}

// The fetch in script.js is the reference that actually decides whether a
// visitor sees fresh numbers.
const scriptPath = path.join(DIST, "script.js");
if (fs.existsSync(scriptPath)) {
    let js = fs.readFileSync(scriptPath, "utf8");
    const before = js;
    js = js.replace(
        /resultsFile:\s*"results\.json(?:\?v=[a-f0-9]+)?"/,
        `resultsFile: "results.json?v=${hashes["results.json"]}"`,
    );
    if (js === before) {
        console.error("  WARNING: could not rewrite resultsFile in script.js — "
                      + "the leaderboard may serve a cached results.json");
        process.exitCode = 1;
    }
    fs.writeFileSync(scriptPath, js);
}

for (const [asset, hash] of Object.entries(hashes)) {
    console.log(`  ${asset} -> ?v=${hash}`);
}
console.log(`Build complete -> ${path.relative(ROOT, DIST)}/`);
