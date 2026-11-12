"""Render 3D → motor de sequência do Horys → folhas, GIFs e métricas (antes × depois).

    python processar.py            (na pasta experimentos/animacao-3d, depois do blender/golem.py)

Antes = render nativo 256 (bruto256). Depois = render 4× (x4) pelo horys_pixel.sequencia com o preset render3d
(escala fixa: uma transformação para a sequência inteira; nada de normalizar a altura por quadro).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1] / "src"))
from horys_pixel import sequencia as S  # noqa: E402
from horys_pixel.sequencia import entradas, registro, spritesheet, validar  # noqa: E402

PALETA_V1 = ["#1a1420", "#2a2531", "#3c3543", "#5f4e42", "#8e7560", "#b8a089", "#ff9a1a", "#6bbf3f", "#7057a8"]
# subpaleta real da referência (15 cores por median cut da vista frontal da ficha + contorno)
_PV3 = AQUI / "referencia" / "paleta_v3.json"
PALETA = json.loads(_PV3.read_text()) if _PV3.exists() else PALETA_V1
GLOW = (0xff, 0x9a, 0x1a)
ACOES = {f"{a}_{d}": n for a, n in (("idle", 4), ("walk", 8)) for d in ("s", "se", "e")}
MS = 125   # 8 fps


def ler(pasta):
    return entradas.de_render3d(pasta)


def gif_lado_a_lado(antes, depois, saida, k=2):
    fr = []
    for a, d in zip(antes, depois):
        h, w = a.shape[:2]
        c = Image.new("RGBA", (w * 2 + 8, h), (205, 205, 210, 255))
        c.alpha_composite(Image.fromarray(a, "RGBA"), (0, 0))
        c.alpha_composite(Image.fromarray(d, "RGBA"), (w + 8, 0))
        fr.append(c.resize((c.width * k, c.height * k), Image.NEAREST).convert("RGB"))
    fr[0].save(saida, save_all=True, append_images=fr[1:], duration=MS, loop=0)


def gif_ampliado(quadros, saida, k=3):
    fr = []
    for q in quadros:
        c = Image.new("RGBA", (q.shape[1], q.shape[0]), (205, 205, 210, 255))
        c.alpha_composite(Image.fromarray(q, "RGBA"))
        fr.append(c.resize((c.width * k, c.height * k), Image.NEAREST).convert("RGB"))
    fr[0].save(saida, save_all=True, append_images=fr[1:], duration=MS, loop=0)


def main():
    rel = {}
    for acao, n in ACOES.items():
        bruto_dir = AQUI / "renders" / f"{acao}_bruto256"
        x4_dir = AQUI / "renders" / f"{acao}_x4"
        man = entradas.ler_manifesto(x4_dir)
        bruto = ler(bruto_dir)
        piv_b = tuple(entradas.ler_manifesto(bruto_dir)["pivo"])
        v_antes = validar.validar(bruto, PALETA, piv_b)
        # escala 1:1 no espaço 4× (a altura máxima do render vira a altura alvo): só a moda reduz para 256
        x4 = ler(x4_dir)
        alt = max(registro.caixa(q)[3] - registro.caixa(q)[1] + 1 for q in x4) / 4
        piv = (man["pivo"][0] / 4, man["pivo"][1] / 4)
        chao = max(registro.caixa(q)[3] for q in x4) / 4
        r = S.processar(str(x4_dir), PALETA, alt, (256, 256), (piv[0], chao), fator=4, proteger={GLOW})
        depois = r["quadros"]
        out = AQUI / "renders" / f"{acao}_horys"
        out.mkdir(exist_ok=True)
        for i, q in enumerate(depois):
            Image.fromarray(q, "RGBA").save(out / f"{i:04d}.png")
        spritesheet.salvar(depois, AQUI / "spritesheets", f"golem_{acao}", MS, acao, (piv[0], chao))  # tag = acao_dir
        spritesheet.salvar(bruto, AQUI / "spritesheets", f"golem_{acao}_bruto", MS, acao, piv_b)
        (AQUI / "previews").mkdir(exist_ok=True)
        gif_lado_a_lado(bruto, depois, AQUI / "previews" / f"{acao}_bruto_vs_horys.gif")
        gif_ampliado(depois, AQUI / "previews" / f"{acao}_horys_3x.gif")
        gif_ampliado(bruto, AQUI / "previews" / f"{acao}_bruto_3x.gif")
        rel[acao] = {"antes": {"aprovado": v_antes["aprovado"], "metricas": v_antes["metricas"],
                               "falhas": [c for c in v_antes["checagens"] if not c["ok"]]},
                     "depois": {"aprovado": r["relatorio"]["validacao"]["aprovado"],
                                "metricas": r["relatorio"]["validacao"]["metricas"],
                                "falhas": [c for c in r["relatorio"]["validacao"]["checagens"] if not c["ok"]],
                                "pisca_antes": r["relatorio"]["pisca_antes"],
                                "pisca_depois": r["relatorio"]["pisca_depois"]}}
        print(f"== {acao}\nANTES  " + validar.resumo(v_antes) + "\nDEPOIS " +
              validar.resumo(r["relatorio"]["validacao"]))
    (AQUI / "metricas.json").write_text(json.dumps(rel, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
