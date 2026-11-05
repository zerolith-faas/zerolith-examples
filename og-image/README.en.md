*[Français](README.md)*

# og-image

A link-preview image (Open Graph, 1200×630), drawn on demand by a Python function. It is what
Slack, LinkedIn, X or Discord show when someone pastes a URL.

**Live:** <https://og-image-fn-539b8643bc44462c815a5ad5a423d976.api.zerolith.fr/?title=Dependency+builds&subtitle=zerolith.fr>

| Parameter | Value |
|-----------|-------|
| `title` | the title, at most 90 characters, cut on a word with "…" |
| `subtitle` | one line under the title, at most 70 characters |
| `theme` | `dark` (default) or `light` |

Put this in the page that shares the link:

```html
<meta property="og:image"
      content="https://<function-url>/?title=My+post&subtitle=blog.example.com">
```

## What it shows

This function needs two packages the base Python image does not ship:

```text
# requirements.txt
pillow==13.0.0
font-source-sans-pro==0.0.1
```

- **Pillow** draws the image. It is a **compiled** library: its wheel depends on the exact
  interpreter version. A `pip install` run on your laptop and copied into the code would not
  load; the platform builds the layer itself, for the runtime you picked.
- **font-source-sans-pro** brings a free font (OFL 1.1). Pillow's built-in font has no accented
  letters: "dépendances" renders as "d▯pendances". A function's code only carries text, so a
  `.ttf` file travels as a package too.

The fonts are loaded once when the pod starts, not on every request.

## Deploying

The dependency build is a step **before** the deploy. Over MCP (or the REST API
`/api/dependencies/builds`):

1. `build_dependencies` with `language: "python"` and the `requirements.txt`;
2. `get_dependency_build` until `ready` (about 15 s for this lockfile);
3. `deploy_function` with `main.py` **and** the same `requirements.txt`, handler `main.handler`.

A deploy whose lockfile has no ready build yet is refused (409) with the steps to follow.
Measured in prod on 2026-11-05: a 9.8 MB compressed layer (26 MB extracted), downloaded in 0.5 s
when the pod starts; rendering one image takes about 160 ms. Cold start (`small` size): 4.2 s on average over three
runs, against 2.3 s for `hello` at the same moment, so about 1.8 s for the layer; warm, 0.15 s.
