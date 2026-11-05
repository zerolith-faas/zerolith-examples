*[Français](README.md)*

# og-image-node

The same link-preview image (Open Graph, 1200×630) as [`og-image`](../og-image/), drawn this time
by a **Node.js** function.

**Live:** <https://og-image-node-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/?title=Node+dependencies&subtitle=zerolith.fr>

Same parameters: `title` (at most 90 characters), `subtitle` (70), `theme` = `dark` or `light`.

## What it shows

Three packages the base Node image does not ship, declared in `package.json` and pinned by
`package-lock.json`:

| Package | Role |
|---------|------|
| `satori` | lays out a JSX-like tree (flexbox, text) and produces an SVG, in plain JavaScript |
| `@resvg/resvg-js` | rasterises the SVG to PNG. A **native** (Rust) binary: `npm ci` installs the variant for the platform, `linux-x64-gnu` here, and skips the eleven others |
| `@fontsource/source-sans-3` | the font, as WOFF: satori does not read WOFF2 |

The handler needs no JSX compiler: a satori node is written
`{ type: 'div', props: { style, children } }`.

**A dependency fixed without waiting for upstream.** After the first build, the vulnerability
indicator (OSV) flagged `fflate@0.7.3` (GHSA-px8p-9vwx-vf98), which satori pins to an exact
version. The flaw is in `unzipSync` on a crafted ZIP archive, which this function never calls; it
was fixed anyway with an npm `overrides`:

```json
"overrides": { "fflate": "0.7.5" }
```

The PNG output is byte-for-byte identical, and the next build flags nothing.

## Deploying

1. Generate the lockfile without running any script: `npm install --package-lock-only --ignore-scripts`;
2. `build_dependencies` with `language: "nodejs22"`, `package.json` **and** `package-lock.json`;
3. `get_dependency_build` until `ready` (about 30 s for this lockfile);
4. `deploy_function` with `main.js`, `package.json` and `package-lock.json`, handler `main.handler`.

Measured in prod on 2026-11-05: an 18.4 MB compressed layer (46 MB, 707 files once extracted).
Cold start (`small` size, six runs): median 4.3 s, against 1.4 s for `timer` (Node, no layer) at the
same moments; downloading the layer takes 1.6 s of it (median). Warm: 0.12 to 0.18 s.
