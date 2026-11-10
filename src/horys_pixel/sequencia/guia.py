"""3.1 · Guia de pose: as poses do plano em SILHUETA, em grade, com a mesma escala e o mesmo chão, para anexar ao prompt
de poses (a fonte é o render do Kiln ou do Noct 3D, já feito)."""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from . import escolha, registro


def grade_silhuetas(quadros: list[np.ndarray], linhas: int, colunas: int, celula: tuple[int, int] = (384, 512),
                    plano: str | None = None, cor_fundo=(255, 255, 255), cor_silhueta=(40, 40, 60),
                    margem: float = 0.10, numerar: bool = True) -> tuple[Image.Image, list[int]]:
    """Escolhe linhas×colunas poses (por 'plano' andar|golpe, ou espaçadas), põe cada silhueta no centro da célula com
    UMA escala só (a mesma altura de referência) e os pés na mesma linha. Devolve (imagem, índices escolhidos)."""
    n = linhas * colunas
    if plano == "andar":
        pick = escolha.escolher_andar(quadros, n)
    elif plano == "golpe":
        pick = escolha.escolher_golpe(quadros, n)
    else:
        pick = sorted(set(np.linspace(0, len(quadros) - 1, min(n, len(quadros))).round().astype(int).tolist()))
    pick = pick[:n]
    cw, ch = celula
    alturas = [(b[3] - b[1] + 1) for q in quadros if (b := registro.caixa(q))]
    alt_ref = float(np.median(alturas)) if alturas else 1.0
    escala = (ch * (1 - 2 * margem)) / max(alt_ref, 1)
    sheet = Image.new("RGB", (cw * colunas, ch * linhas), cor_fundo)
    d = ImageDraw.Draw(sheet)
    chao = int(ch * (1 - margem))
    for k, i in enumerate(pick):
        q = quadros[i]
        b = registro.caixa(q)
        r, c = divmod(k, colunas)
        ox, oy = c * cw, r * ch
        d.line([ox + 8, oy + chao, ox + cw - 8, oy + chao], fill=(200, 200, 200))
        if b:
            sil = np.zeros((*q.shape[:2], 4), np.uint8)
            sil[q[..., 3] >= 128] = (*cor_silhueta, 255)
            im = Image.fromarray(sil, "RGBA")
            nw, nh = max(1, round(im.width * escala)), max(1, round(im.height * escala))
            im = im.resize((nw, nh), Image.NEAREST)
            px, py = registro.pivo_dos_pes(np.array(im))
            sheet.paste(im, (round(ox + cw / 2 - px), round(oy + chao - py)), im)
        if numerar:
            d.text((ox + 8, oy + 6), str(k + 1), fill=(120, 120, 120))
    return sheet, pick
