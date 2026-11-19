"""Texto do pedido ao gerador de imagem (ChatGPT, Codex ou outro), preenchido com os números do jogo e do asset.
O formato é o que leitura.py sabe ler sem perder nada; o porquê de cada item está em prompt.md."""
from __future__ import annotations

from . import asset as AS
from . import paleta as P

MODELO = """Gere UMA imagem de pixel art de um personagem para um jogo 2D top-down.

Personagem: {descricao}

Formato obrigatório:
1. Três vistas do MESMO personagem lado a lado, da esquerda para a direita: FRENTE, LADO (olhando para a DIREITA) e
   COSTAS. Nada além disso: sem texto, sem rótulo, sem moldura, sem chão e sem sombra no chão.
2. Câmera: top-down 3/4, inclinada {angulo}° acima do horizonte (vê o topo da cabeça e a frente do corpo), igual nas
   três vistas, sem perspectiva.
3. Escala: cada figura com exatamente {alvo} pixels de altura, do topo da cabeça à sola do pé. As três com a mesma
   altura e os pés na mesma linha horizontal.
4. Pixel art de verdade: pixels quadrados, grandes e nítidos, todos do mesmo tamanho (a imagem é a pixel art
   ampliada sem suavização). Sem antisserrilhado, degradê, desfoque, ruído ou meio pixel.
5. Contorno escuro de 1 pixel em volta de toda a figura{tinta}.
6. Cores: no máximo {max_cores} no total, 2 a 3 tons por material (sombra, base, luz), luz vindo de cima à
   esquerda.{paleta}
7. Formas simples e grandes: nenhum detalhe menor que 2×2 pixels; olhos com 1 a 2 pixels.
8. Fundo inteiro de uma cor só, #FF00FF (magenta), sem degradê. O magenta não pode aparecer no personagem.
9. Figura inteira com margem em volta (nada encostando na borda), em pé, postura neutra, braços um pouco afastados
   do corpo, sem objetos soltos no ar.
Imagem de 1536×1024 (paisagem)."""


def gerar(a: AS.Asset, jogo: dict) -> str:
    tinta, paleta = "", ""
    if a.paleta.exists():
        pal = P.ler(a.paleta)
        tinta = f" ({pal['tinta']})"
        linhas = [f"   - {n}: {', '.join(f['rampa'])}" for n, f in pal["familias"].items()]
        paleta = "\n   Use SÓ estas cores (cada linha é um material, do escuro ao claro):\n" + "\n".join(linhas)
    return MODELO.format(descricao=(a.cfg.get("descricao") or "<descreva o personagem: função, roupa, 3 cores "
                                    "principais, silhueta numa frase, o que ele NÃO pode ter>"),
                         angulo=jogo["angulo"], alvo=a.alvo_px(jogo), max_cores=jogo["max_cores"], tinta=tinta,
                         paleta=paleta)
