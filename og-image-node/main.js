// zerolith · exemple « image d'aperçu » (Open Graph), version Node.js.
//
// Le même PNG 1200×630 que l'exemple Python `og-image`, dessiné autrement : satori met en page
// un arbre de type JSX et produit un SVG, resvg le rastérise en PNG. Trois paquets absents de
// l'image de base, construits par la plateforme à partir du `package-lock.json` voisin
// (build_dependencies, puis deploy) :
//
//   satori                    mise en page (flexbox) + texte → SVG, en JavaScript pur
//   @resvg/resvg-js           SVG → PNG, un binaire NATIF (Rust) : le paquet choisit, à
//                             l'installation, la variante de la plateforme (linux-x64-gnu ici)
//   @fontsource/source-sans-3 la police, en WOFF (satori ne lit pas le WOFF2)
//
//   GET /?title=Mon+article
//   GET /?title=Mon+article&subtitle=blog.example.com&theme=light

const fs = require('node:fs');
const satori = require('satori').default;
const { Resvg } = require('@resvg/resvg-js');

const W = 1200;
const H = 630;
const TITLE_MAX = 90;
const SUBTITLE_MAX = 70;
// La largeur utile : l'image moins le liseré (16) et les deux marges (80).
const TEXT_W = W - 16 - 2 * 80;

const THEMES = {
  dark: { bg: '#0b1220', ink: '#f1f5f9', dim: '#94a3b8', accent: '#1fa3a7' },
  light: { bg: '#f8fafc', ink: '#0f172a', dim: '#475569', accent: '#0e7c80' },
};

// Lues une fois, au démarrage du pod, pas à chaque requête.
const font = (weight) =>
  fs.readFileSync(
    require.resolve(`@fontsource/source-sans-3/files/source-sans-3-latin-${weight}-normal.woff`),
  );
const FONTS = [
  { name: 'Source Sans 3', data: font(400), weight: 400, style: 'normal' },
  { name: 'Source Sans 3', data: font(700), weight: 700, style: 'normal' },
];

// Espaces normalisés, coupé à `limit` caractères sur une limite de mot, avec « … ».
function clip(text, limit) {
  const t = String(text || '').split(/\s+/).filter(Boolean).join(' ');
  if (t.length <= limit) return t;
  const cut = t.slice(0, limit).replace(/\s+\S*$/, '') || t.slice(0, limit);
  return cut.replace(/[\s,;:.-]+$/, '') + '…';
}

// Un nœud satori : la forme objet de JSX, pour ne pas avoir besoin d'un compilateur.
const h = (type, style, children) => ({ type, props: { style, children } });

function tree(title, subtitle, t) {
  return h('div', {
    width: W, height: H, display: 'flex', flexDirection: 'column', justifyContent: 'center',
    paddingLeft: 80, paddingRight: 80, background: t.bg, borderLeft: `16px solid ${t.accent}`,
    fontFamily: 'Source Sans 3',
  }, [
    // satori replie le texte et, avec lineClamp, finit la troisième ligne par « … ».
    h('div', {
      width: TEXT_W, fontSize: title.length > 50 ? 64 : 80, fontWeight: 700, color: t.ink,
      lineHeight: 1.15, display: 'block', lineClamp: 3,
    }, title),
    subtitle
      ? h('div', {
        width: TEXT_W, fontSize: 38, color: t.dim, marginTop: 24, whiteSpace: 'nowrap',
        overflow: 'hidden', textOverflow: 'ellipsis',
      }, subtitle)
      : h('div', { display: 'none' }, ''),
    h('div', {
      position: 'absolute', left: 80, bottom: 60, fontSize: 30, fontWeight: 700, color: t.accent,
    }, 'zerolith'),
  ]);
}

exports.handler = async (request) => {
  const q = request.query || {};
  const title = clip(q.title, TITLE_MAX) || 'Hello from zerolith';
  const subtitle = clip(q.subtitle, SUBTITLE_MAX);
  const theme = q.theme || 'dark';
  if (!THEMES[theme]) return [400, { error: `theme must be one of ${Object.keys(THEMES)}` }];

  const started = performance.now();
  const svg = await satori(tree(title, subtitle, THEMES[theme]), { width: W, height: H, fonts: FONTS });
  const png = new Resvg(svg).render().asPng();
  return [200, png, {
    'Content-Type': 'image/png',
    'Cache-Control': 'public, max-age=86400',
    // Une image publique : n'importe quelle page peut la récupérer en fetch.
    'Access-Control-Allow-Origin': '*',
    'X-Render-Ms': (performance.now() - started).toFixed(0),
  }];
};
