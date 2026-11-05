"""zerolith · exemple « image d'aperçu » (Open Graph).

Une fonction Python qui DESSINE un PNG de 1200×630, l'image que Slack, LinkedIn, X ou
Discord affichent quand on colle un lien. Elle s'appuie sur deux paquets absents de
l'image de base, construits par la plateforme à partir du `requirements.txt` voisin
(build_dependencies, puis deploy) :

    pillow                 le dessin, une bibliothèque COMPILÉE (wheel propre à l'interpréteur)
    font-source-sans-pro   une police libre (OFL) livrée comme un paquet : la police par
                           défaut de Pillow n'a pas d'accents, « dépendances » y perd son é

    GET /?title=Mon+article
    GET /?title=Mon+article&subtitle=blog.example.com&theme=light

À poser dans la page qui partage le lien :

    <meta property="og:image" content="https://<cette-fonction>/?title=Mon+article">
"""

import io
import os
import time

import font_source_sans_pro
from PIL import Image, ImageDraw, ImageFont
from PIL import __version__ as PIL_VERSION

W, H = 1200, 630
MARGIN = 80
TITLE_MAX = 90
SUBTITLE_MAX = 70

THEMES = {
    "dark": {"bg": "#0b1220", "ink": "#f1f5f9", "dim": "#94a3b8", "accent": "#1fa3a7"},
    "light": {"bg": "#f8fafc", "ink": "#0f172a", "dim": "#475569", "accent": "#0e7c80"},
}


def _font(weight, size):
    path = os.path.join(font_source_sans_pro.font_directory, f"SourceSansPro-{weight}.ttf")
    return ImageFont.truetype(path, size)


# Chargées une fois, au démarrage du pod, pas à chaque requête.
TITLE_FONTS = {size: _font("Bold", size) for size in (80, 68, 56)}
SUBTITLE_FONT = _font("Regular", 38)
BRAND_FONT = _font("Semibold", 30)


def _clip(text, limit):
    """Espaces normalisés, coupé à `limit` caractères sur une limite de mot, avec « … »."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return cut.rstrip(" ,;:.-") + "…"


def _wrap(draw, text, font, width):
    """Coupe `text` en lignes qui tiennent dans `width` pixels (mot par mot)."""
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if draw.textlength(candidate, font=font) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _title_lines(draw, title):
    """La plus grande taille où le titre tient en trois lignes."""
    for size, font in TITLE_FONTS.items():
        lines = _wrap(draw, title, font, W - 2 * MARGIN)
        if len(lines) <= 3:
            return font, size, lines
    return font, size, [*lines[:2], _fit(draw, lines[2] + " …", font, W - 2 * MARGIN)]


def _fit(draw, text, font, width):
    """`text` tel quel s'il tient dans `width` pixels, sinon raccourci avec « … »."""
    if draw.textlength(text, font=font) <= width:
        return text
    text = text.removesuffix(" …")
    while text and draw.textlength(text + "…", font=font) > width:
        text = text.rsplit(" ", 1)[0] if " " in text else text[:-1]
    return text.rstrip(" ,;:.-") + "…"


def render(title, subtitle, theme):
    t = THEMES[theme]
    img = Image.new("RGB", (W, H), t["bg"])
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, 16, H), fill=t["accent"])

    font, size, lines = _title_lines(draw, title)
    line_h = int(size * 1.2)
    y = (H - line_h * len(lines)) // 2 - 30
    for line in lines:
        # Un mot plus large que l'image (une URL, un hash) est raccourci, pas débordé.
        draw.text((MARGIN, y), _fit(draw, line, font, W - 2 * MARGIN), font=font, fill=t["ink"])
        y += line_h

    if subtitle:
        subtitle = _fit(draw, subtitle, SUBTITLE_FONT, W - 2 * MARGIN)
        draw.text((MARGIN, y + 24), subtitle, font=SUBTITLE_FONT, fill=t["dim"])

    draw.text((MARGIN, H - MARGIN), "zerolith", font=BRAND_FONT, fill=t["accent"])

    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def handler(request):
    q = request.query
    title = _clip(q.get("title", ""), TITLE_MAX) or "Hello from zerolith"
    subtitle = _clip(q.get("subtitle", ""), SUBTITLE_MAX)
    theme = q.get("theme", "dark")
    if theme not in THEMES:
        return 400, {"error": f"theme must be one of {sorted(THEMES)}"}

    started = time.monotonic()
    png = render(title, subtitle, theme)
    return (
        200,
        png,
        {
            "Content-Type": "image/png",
            # Les plateformes sociales mettent l'image en cache de leur côté ; un jour ici
            # évite qu'un navigateur la redemande à chaque affichage.
            "Cache-Control": "public, max-age=86400",
            # Une image publique : n'importe quelle page peut la récupérer en fetch (la galerie
            # de la doc zerolith le fait, sa CSP n'autorisant que les images `data:`).
            "Access-Control-Allow-Origin": "*",
            "X-Render-Ms": f"{(time.monotonic() - started) * 1000:.0f}",
            "X-Pillow-Version": PIL_VERSION,
        },
    )
