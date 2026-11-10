"""Grade exata: reduz uma referência ao tamanho do sprite e devolve a matriz XY real.

Uso:
  python tools/grade_exata.py ref.png --tam 32 --cores 12 --saida pasta [--recorte x0,y0,x1,y1] [--fundo auto|#rrggbb|nenhum]

Saídas na pasta:
  sprite_1x.png        sprite no tamanho final (fundo transparente)
  sprite_grade.png     ampliado com grade e coordenadas X/Y (para conferência)
  matriz.json          paleta + linhas (formato pixel_map do horys/aseprite)
  matriz.txt           mesma matriz legível, com régua de colunas
"""
import argparse, json, os, string
from PIL import Image, ImageDraw

CHAVES = string.ascii_letters + string.digits


def cor_fundo(img):
    w, h = img.size
    cantos = [img.getpixel(p)[:3] for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]]
    return max(set(cantos), key=cantos.count)


def perto(a, b, tol):
    return sum((x - y) ** 2 for x, y in zip(a, b)) <= tol * tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ref")
    ap.add_argument("--tam", type=int, default=32, help="maior lado do sprite em pixels")
    ap.add_argument("--cores", type=int, default=12)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--recorte", default=None)
    ap.add_argument("--fundo", default="auto")
    ap.add_argument("--tol", type=int, default=110, help="tolerância da cor de fundo")
    ap.add_argument("--zoom", type=int, default=16)
    a = ap.parse_args()
    os.makedirs(a.saida, exist_ok=True)

    img = Image.open(a.ref).convert("RGBA")
    if a.recorte:
        img = img.crop(tuple(int(v) for v in a.recorte.split(",")))

    # fundo -> transparente
    if a.fundo != "nenhum":
        fc = cor_fundo(img) if a.fundo == "auto" else tuple(int(a.fundo[i:i + 2], 16) for i in (1, 3, 5))
        px = img.load()
        for y in range(img.height):
            for x in range(img.width):
                if perto(px[x, y][:3], fc, a.tol):
                    px[x, y] = (0, 0, 0, 0)

    # recorta ao conteúdo
    bb = img.getbbox()
    if bb:
        img = img.crop(bb)

    # reduz pelo maior lado: média de bloco (BOX) e alfa por cobertura
    esc = a.tam / max(img.size)
    w, h = max(1, round(img.width * esc)), max(1, round(img.height * esc))
    alfa = img.getchannel("A")
    base = Image.new("RGB", img.size, (0, 0, 0))
    base.paste(img.convert("RGB"), mask=alfa)
    soma = base.resize((w, h), Image.BOX).load()
    cob = alfa.resize((w, h), Image.BOX)
    peq = Image.new("RGB", (w, h))
    for y in range(h):
        for x in range(w):
            c = cob.getpixel((x, y)) / 255
            if c > 0:  # desfaz a mistura com o preto do fundo
                peq.putpixel((x, y), tuple(min(255, round(v / c)) for v in soma[x, y]))

    # limita paleta; MAXCOVERAGE guarda cores de destaque (olho, musgo)
    q = peq.quantize(colors=a.cores, method=Image.Quantize.MAXCOVERAGE, dither=Image.Dither.NONE)
    rgb = q.convert("RGB")
    final = Image.new("RGBA", (w, h))
    for y in range(h):
        for x in range(w):
            if cob.getpixel((x, y)) >= 128:
                final.putpixel((x, y), rgb.getpixel((x, y)) + (255,))
    final.save(os.path.join(a.saida, "sprite_1x.png"))

    # matriz
    cores = {}
    linhas = []
    for y in range(h):
        s = ""
        for x in range(w):
            p = final.getpixel((x, y))
            if p[3] == 0:
                s += "."
                continue
            hx = "#%02x%02x%02x" % p[:3]
            if hx not in cores:
                cores[hx] = CHAVES[len(cores)]
            s += cores[hx]
        linhas.append(s)
    paleta = {k: hx for hx, k in cores.items()}
    with open(os.path.join(a.saida, "matriz.json"), "w", encoding="utf-8") as f:
        json.dump({"largura": w, "altura": h, "palette": paleta, "rows": linhas}, f, indent=1)
    with open(os.path.join(a.saida, "matriz.txt"), "w", encoding="utf-8") as f:
        f.write("    " + "".join(str(x // 10) for x in range(w)) + "\n")
        f.write("    " + "".join(str(x % 10) for x in range(w)) + "\n")
        for y, l in enumerate(linhas):
            f.write(f"{y:3d} {l}\n")
        f.write("\npaleta:\n" + "\n".join(f"  {k} = {v}" for k, v in paleta.items()) + "\n")

    # imagem com grade e coordenadas
    z, m = a.zoom, 24
    g = Image.new("RGB", (w * z + m, h * z + m), (40, 40, 48))
    for y in range(h):
        for x in range(w):
            p = final.getpixel((x, y))
            c = p[:3] if p[3] else ((70, 70, 80) if (x + y) % 2 else (60, 60, 70))
            g.paste(c, (m + x * z, m + y * z, m + (x + 1) * z, m + (y + 1) * z))
    d = ImageDraw.Draw(g)
    for x in range(w + 1):
        d.line([(m + x * z, m), (m + x * z, m + h * z)], fill=(0, 0, 0) if x % 8 else (255, 80, 80))
    for y in range(h + 1):
        d.line([(m, m + y * z), (m + w * z, m + y * z)], fill=(0, 0, 0) if y % 8 else (255, 80, 80))
    for x in range(0, w, 2):
        d.text((m + x * z + 2, 6), str(x), fill=(220, 220, 220))
    for y in range(0, h, 2):
        d.text((2, m + y * z + 2), str(y), fill=(220, 220, 220))
    g.save(os.path.join(a.saida, "sprite_grade.png"))
    print(f"ok {w}x{h}, {len(paleta)} cores -> {a.saida}")


if __name__ == "__main__":
    main()
