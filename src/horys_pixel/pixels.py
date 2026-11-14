"""Pixels: mapa de letras <-> RGBA, base64, diferenças e prévias (cor, cinza, silhueta, 1x)."""
from __future__ import annotations

import base64
import io
import json
import string
from pathlib import Path

import numpy as np
from PIL import Image

# letras de cor: nunca '.', espaço, '#' (marcador interno do grade.py) nem '-' (linha '---' vira cabeçalho)
LETRAS = (string.ascii_lowercase + string.ascii_uppercase + string.digits + "!$%&*+/:;<=>?^_~"
          + "àáâãäåæçèéêëìíîïñòóôõöøùúûüýÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÑÒÓÔÕÖØÙÚÛÜÝ")


# ---------------------------------------------------------------- cor

def hex_rgba(h: str) -> tuple[int, int, int, int]:
    s = str(h).strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        s += "ff"
    if len(s) != 8:
        raise ValueError(f"cor inválida: {h!r} (use #rrggbb ou #rrggbbaa)")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]


def rgba_hex(c) -> str:
    r, g, b, a = (int(x) for x in c)
    return f"#{r:02x}{g:02x}{b:02x}" if a == 255 else f"#{r:02x}{g:02x}{b:02x}{a:02x}"


# ---------------------------------------------------------------- base64

def b64_de_array(a: np.ndarray) -> str:
    return base64.b64encode(np.ascontiguousarray(a, dtype=np.uint8).tobytes()).decode("ascii")


def array_de_b64(s: str, w: int, h: int, canais: int = 4) -> np.ndarray:
    dados = base64.b64decode(s)
    esperado = w * h * canais
    if len(dados) != esperado:
        raise ValueError(f"base64 com {len(dados)} bytes, esperado {esperado} ({w}x{h}x{canais})")
    return np.frombuffer(dados, dtype=np.uint8).reshape(h, w, canais) if canais > 1 else \
        np.frombuffer(dados, dtype=np.uint8).reshape(h, w)


def png_b64(img: np.ndarray | Image.Image) -> str:
    im = img if isinstance(img, Image.Image) else Image.fromarray(np.asarray(img, np.uint8), "RGBA")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------- mapa de letras

def carregar_mapa(args: dict) -> dict:
    """Junta os campos do pedido com um arquivo .json opcional ('arquivo')."""
    dados = dict(args)
    arq = dados.pop("arquivo", None)
    if arq:
        extra = json.loads(Path(arq).read_text(encoding="utf-8"))
        for k, v in extra.items():
            dados.setdefault(k, v)
    return dados


def _rot(linhas: list[str], flip: str | None) -> list[str]:
    if not flip:
        return linhas
    out = list(linhas)
    if "h" in flip:
        out = [l[::-1] for l in out]
    if "v" in flip:
        out = out[::-1]
    return out


def compor_mapa(paleta: dict, linhas: list[str] | None, stamps: dict | None = None,
                place: list | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Monta (rgba HxWx4, máscara HxW) a partir de paleta + linhas e carimbos.

    '.' e espaço = não toca. Uma chave mapeada para '#00000000' apaga.
    """
    linhas = list(linhas or [])
    camadas = [(0, 0, linhas, paleta)]
    for item in place or []:
        nome, x, y = item[0], int(item[1]), int(item[2])
        flip = item[3] if len(item) > 3 else None
        st = (stamps or {}).get(nome)
        if st is None:
            raise ValueError(f"carimbo '{nome}' não definido em stamps")
        pal = dict(paleta)
        pal.update(st.get("palette") or st.get("paleta") or {})
        camadas.append((x, y, _rot(st["rows"] if "rows" in st else st["linhas"], flip), pal))
    w = max((x + max((len(l) for l in ls), default=0)) for x, y, ls, _ in camadas) if camadas else 0
    h = max((y + len(ls)) for x, y, ls, _ in camadas) if camadas else 0
    rgba = np.zeros((h, w, 4), np.uint8)
    masc = np.zeros((h, w), np.uint8)
    cache: dict[str, tuple] = {}
    for x0, y0, ls, pal in camadas:
        for i, l in enumerate(ls):
            for j, ch in enumerate(l):
                if ch in ". ":
                    continue
                if ch not in pal:
                    raise ValueError(f"letra '{ch}' (linha {i}, coluna {j}) sem cor na paleta")
                cor = cache.get(pal[ch]) or hex_rgba(pal[ch])
                cache[pal[ch]] = cor
                rgba[y0 + i, x0 + j] = cor
                masc[y0 + i, x0 + j] = 1
    return rgba, masc


def para_linhas(rgba: np.ndarray, paleta: dict | None = None) -> tuple[dict, list[str], list[str]]:
    """RGBA -> (paleta letra->hex, linhas, avisos). Reaproveita as letras da paleta dada."""
    paleta = dict(paleta or {})
    inv = {}
    for k, v in paleta.items():
        try:
            inv[rgba_hex(hex_rgba(v))] = k
        except ValueError:
            pass
    livres = [c for c in LETRAS if c not in paleta and c != "."]
    avisos = []
    linhas = []
    for row in rgba:
        s = []
        for px in row:
            if px[3] == 0:
                s.append(".")
                continue
            hx = rgba_hex(px)
            k = inv.get(hx)
            if k is None:
                if not livres:
                    raise ValueError(f"cores demais para letras (mais de {len(LETRAS)})")
                k = livres.pop(0)
                inv[hx] = k
                paleta[k] = hx
            s.append(k)
        linhas.append("".join(s).rstrip(".") or "")
    usadas = set("".join(linhas)) - {"."}
    paleta = {k: v for k, v in paleta.items() if k in usadas}
    return paleta, linhas, avisos


# ---------------------------------------------------------------- prévias

def _escala(img: Image.Image, k: int) -> Image.Image:
    return img.resize((img.width * k, img.height * k), Image.NEAREST)


def sobre_fundo(rgba: np.ndarray, fundo=(138, 146, 144)) -> Image.Image:
    base = Image.new("RGBA", (rgba.shape[1], rgba.shape[0]), (*fundo, 255))
    base.alpha_composite(Image.fromarray(rgba, "RGBA"))
    return base


def cinza(rgba: np.ndarray) -> np.ndarray:
    rgb = rgba[..., :3].astype(np.float32)
    l = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.uint8)
    out = rgba.copy()
    out[..., 0] = out[..., 1] = out[..., 2] = l
    return out


def silhueta(rgba: np.ndarray) -> np.ndarray:
    out = np.zeros_like(rgba)
    m = rgba[..., 3] > 0
    out[m] = (24, 18, 44, 255)
    return out


def recorte(rgba: np.ndarray, margem: int = 2) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(rgba[..., 3] > 0)
    if ys.size == 0:
        return 0, 0, rgba.shape[1], rgba.shape[0]
    x0, y0 = max(0, xs.min() - margem), max(0, ys.min() - margem)
    x1, y1 = min(rgba.shape[1], xs.max() + 1 + margem), min(rgba.shape[0], ys.max() + 1 + margem)
    return int(x0), int(y0), int(x1), int(y1)


def critica(rgba: np.ndarray, limite: int = 640, cortar: bool = True) -> Image.Image:
    """Uma imagem pequena: cor | cinza (valores) | silhueta | tamanho real (1x e 2x)."""
    if cortar:
        x0, y0, x1, y1 = recorte(rgba, 3)
        rgba = rgba[y0:y1, x0:x1]
    h, w = rgba.shape[:2]
    k = max(1, min(8, limite // max(1, 3 * w + 3 * w // 4)))
    paineis = [sobre_fundo(rgba), sobre_fundo(cinza(rgba)), sobre_fundo(silhueta(rgba), (220, 220, 210))]
    grandes = [_escala(p, k) for p in paineis]
    real1 = sobre_fundo(rgba, (104, 160, 87))
    real2 = _escala(real1, 2)
    larg = sum(g.width for g in grandes) + real2.width + 8 * 5
    alt = max(grandes[0].height, real1.height + real2.height + 8)
    tela = Image.new("RGBA", (larg, alt + 16), (40, 40, 48, 255))
    x = 8
    for g in grandes:
        tela.paste(g, (x, 8))
        x += g.width + 8
    tela.paste(real1, (x, 8))
    tela.paste(real2, (x, 8 + real1.height + 8))
    return tela


def ampliar(rgba: np.ndarray, escala: int = 0, limite: int = 768) -> Image.Image:
    h, w = rgba.shape[:2]
    k = escala or max(1, min(12, limite // max(w, h, 1)))
    return _escala(sobre_fundo(rgba), k)


# ---------------------------------------------------------------- diferenças

def diff_bbox(a: np.ndarray, b: np.ndarray):
    if a.shape != b.shape:
        return (0, 0, b.shape[1], b.shape[0]), int(b.shape[0] * b.shape[1])
    d = np.any(a != b, axis=-1)
    if not d.any():
        return None, 0
    ys, xs = np.nonzero(d)
    return (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1), int(d.sum())


# ---------------------------------------------------------------- comparar, onion, filmstrip, diff

def compor_camadas(camadas: list[np.ndarray]) -> np.ndarray:
    """Empilha camadas RGBA (de baixo para cima) com alpha."""
    if not camadas:
        raise ValueError("nenhuma camada")
    base = Image.new("RGBA", (camadas[0].shape[1], camadas[0].shape[0]), (0, 0, 0, 0))
    for c in camadas:
        base.alpha_composite(Image.fromarray(np.ascontiguousarray(c), "RGBA"))
    return np.asarray(base).copy()


def lado_a_lado(imagens: list[np.ndarray], limite: int = 1024, fundo=(138, 146, 144)) -> Image.Image:
    """Painéis do mesmo tamanho, lado a lado, na mesma escala inteira."""
    h = max(i.shape[0] for i in imagens)
    w = max(i.shape[1] for i in imagens)
    k = max(1, min(12, limite // max(1, (w + 2) * len(imagens))))
    tela = Image.new("RGBA", ((w * k + 8) * len(imagens) + 8, h * k + 16), (40, 40, 48, 255))
    for n, i in enumerate(imagens):
        tela.paste(_escala(sobre_fundo(i, fundo), k), (8 + n * (w * k + 8), 8))
    return tela


def onion(alvo: np.ndarray, vizinhos: list[np.ndarray], opacidade: int = 90) -> np.ndarray:
    """O quadro alvo opaco sobre os vizinhos fantasmas (mais antigo primeiro)."""
    camadas = []
    for v in vizinhos:
        f = v.copy()
        f[..., 3] = (f[..., 3].astype(np.uint16) * opacidade // 255).astype(np.uint8)
        camadas.append(f)
    return compor_camadas(camadas + [alvo])


def filmstrip(quadros: list[np.ndarray], limite: int = 1400) -> Image.Image:
    n = len(quadros)
    cols = min(n, 8)
    linhas = (n + cols - 1) // cols
    h, w = quadros[0].shape[:2]
    k = max(1, min(8, limite // max(1, (w + 2) * cols)))
    tela = Image.new("RGBA", (cols * (w * k + 6) + 6, linhas * (h * k + 6) + 6), (40, 40, 48, 255))
    for i, q in enumerate(quadros):
        r, c = divmod(i, cols)
        tela.paste(_escala(sobre_fundo(q), k), (6 + c * (w * k + 6), 6 + r * (h * k + 6)))
    return tela


def diff_texto(antes: np.ndarray, depois: np.ndarray, paleta: dict | None = None) -> tuple[str, dict, int]:
    """Grade de texto: '.' igual, '-' apagado, letra = cor nova. Devolve (texto, paleta, nº mudado)."""
    pal, linhas, _ = para_linhas(depois, paleta)
    mud = np.any(antes != depois, axis=-1)
    apag = mud & (depois[..., 3] == 0)
    out = []
    for y in range(depois.shape[0]):
        lin = linhas[y] if y < len(linhas) else ""
        lin = lin.ljust(depois.shape[1], ".")
        out.append("".join("-" if apag[y, x] else (lin[x] if mud[y, x] else ".") for x in range(depois.shape[1])))
    return "\n".join(out), pal, int(mud.sum())


# ---------------------------------------------------------------- trava de paleta (CIELAB ΔE76)

def _lab(hx: str) -> np.ndarray:
    r, g, b, _ = hex_rgba(hx)
    c = np.array([r, g, b], np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    xyz = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]]) @ c
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def travar_paleta(paleta: dict, permitidas: list[str]) -> tuple[dict, list[tuple[str, str, str, float]]]:
    """Troca cada cor da 'paleta' (letra->hex) pela permitida mais próxima. Transparente fica.
    Devolve (paleta nova, [(letra, de, para, ΔE)] das que mudaram)."""
    alvos = [(h, _lab(h)) for h in permitidas]
    if not alvos:
        return dict(paleta), []
    nova, movidas = {}, []
    for k, v in paleta.items():
        if hex_rgba(v)[3] == 0:
            nova[k] = v
            continue
        lv = _lab(v)
        h, d = min(((h, float(np.linalg.norm(lv - lab))) for h, lab in alvos), key=lambda t: t[1])
        a = hex_rgba(v)[3]
        para = h if a == 255 else h[:7] + f"{a:02x}"
        nova[k] = para
        if para.lower()[:7] != v.lower()[:7]:
            movidas.append((k, v, para, round(d, 1)))
    return nova, movidas
