"""TileSet do Godot 4 (.tres) a partir de uma folha de tiles em PNG, com o layout blob47 de autotile (terreno).

Portado do aseprite-ai-artist (pebbly, MIT, v0.8.3, `tileset` op 'export' e `blob47_masks` da extensão Lua),
reimplementado em Python. Diferenças: lê uma folha PNG (não o tileset do Aseprite), e o .tres do blob47 já sai
com o conjunto de terreno do Godot (peering bits de lados e cantos); o original só escrevia o wangset do Tiled.

Copyright (c) pebbly (aseprite-ai-artist), licença MIT: o aviso de copyright e a permissão valem para as partes
derivadas deste arquivo.

blob47: das 256 vizinhanças de 8 bits, um canto só conta quando os dois lados ao lado dele também estão cheios.
Reduzindo as 256 por essa regra sobram exatamente 47 máscaras; em ordem crescente, é a ordem em que quase todo
tileset blob47 é desenhado. A conta é feita, não fixada: se não der 47, a exportação recusa em vez de escrever um
terreno que encaixaria errado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# bits na ordem do wangid do Tiled
N, NE, E, SE, S, SW, W, NW = 1, 2, 4, 8, 16, 32, 64, 128

# bit -> nome do peering bit do Godot 4 (TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES)
PEERING_GODOT = (
    (E, "right_side"), (SE, "bottom_right_corner"), (S, "bottom_side"), (SW, "bottom_left_corner"),
    (W, "left_side"), (NW, "top_left_corner"), (N, "top_side"), (NE, "top_right_corner"),
)


def reduzir_mascara(m: int) -> int:
    """Tira o canto que não tem os dois lados vizinhos cheios (ele não muda o desenho do tile)."""
    out = int(m) & 0xFF
    for canto, a, b in ((NE, N, E), (SE, S, E), (SW, S, W), (NW, N, W)):
        if out & canto and not (out & a and out & b):
            out &= ~canto
    return out


def blob47_mascaras() -> list[int]:
    """As 47 máscaras canônicas do blob, em ordem crescente (a ordem do tileset)."""
    return sorted({reduzir_mascara(m) for m in range(256)})


def mascara_de_vizinhos(cheio: np.ndarray, x: int, y: int) -> int:
    """Máscara reduzida da célula (x, y) de um mapa booleano de terreno (fora do mapa = vazio)."""
    h, w = cheio.shape
    m = 0
    for bit, dx, dy in ((N, 0, -1), (NE, 1, -1), (E, 1, 0), (SE, 1, 1), (S, 0, 1), (SW, -1, 1), (W, -1, 0),
                        (NW, -1, -1)):
        xx, yy = x + dx, y + dy
        if 0 <= xx < w and 0 <= yy < h and cheio[yy, xx]:
            m |= bit
    return reduzir_mascara(m)


@dataclass
class Folha:
    tile_w: int
    tile_h: int
    colunas: int
    linhas: int
    margem: int = 0
    espaco: int = 0
    vazios: list[int] = field(default_factory=list)   # slots (linha-major) totalmente transparentes

    def coord(self, slot: int) -> tuple[int, int]:
        return slot % self.colunas, slot // self.colunas


def fatiar(folha: np.ndarray, tile_w: int, tile_h: int, margem: int = 0, espaco: int = 0) -> Folha:
    """Grade de tiles da folha (RGBA). Slot = índice linha-major; anota os slots vazios."""
    if tile_w < 1 or tile_h < 1:
        raise ValueError("tile_w e tile_h precisam ser maiores que zero")
    H, W = folha.shape[:2]
    colunas = (W - 2 * margem + espaco) // (tile_w + espaco)
    linhas = (H - 2 * margem + espaco) // (tile_h + espaco)
    if colunas < 1 or linhas < 1:
        raise ValueError(f"a folha {W}×{H} não tem nenhum tile de {tile_w}×{tile_h}")
    f = Folha(tile_w, tile_h, int(colunas), int(linhas), margem, espaco)
    alfa = folha[..., 3] if folha.ndim == 3 and folha.shape[2] == 4 else np.full((H, W), 255, np.uint8)
    for slot in range(f.colunas * f.linhas):
        cx, cy = f.coord(slot)
        x0 = margem + cx * (tile_w + espaco)
        y0 = margem + cy * (tile_h + espaco)
        if not alfa[y0:y0 + tile_h, x0:x0 + tile_w].any():
            f.vazios.append(slot)
    return f


def _cor_godot(hx: str) -> str:
    s = hx.strip().lstrip("#")
    r, g, b = (int(s[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return f"Color({r:.4g}, {g:.4g}, {b:.4g}, 1)"


@dataclass
class ResultadoTres:
    texto: str
    tiles: int
    terreno: dict[int, int]        # slot -> máscara (só no blob47)
    avisos: list[str]


def godot_tres(folha: Folha, textura: str, layout: str = "grid", *, pular: int = 0,
               mascaras: list[int] | None = None, nome_terreno: str = "terreno",
               cor_terreno: str = "#5a9e4b", incluir_vazios: bool = False) -> ResultadoTres:
    """Texto do TileSet do Godot 4 (format=3) com uma fonte de atlas.

    layout 'grid': um tile por slot não vazio (ou todos, com incluir_vazios).
    layout 'blob47': os 47 tiles começam no slot 'pular' em ordem canônica (blob47_mascaras(), ou 'mascaras' se a
    folha usa outra ordem) e cada um recebe terrain_set 0, terrain 0 e os peering bits da sua máscara.
    'textura' é o caminho do PNG no projeto Godot (res://...)."""
    avisos: list[str] = []
    total = folha.colunas * folha.linhas
    terreno: dict[int, int] = {}
    if layout == "grid":
        slots = [s for s in range(total) if incluir_vazios or s not in folha.vazios]
        if not slots:
            raise ValueError("a folha não tem nenhum tile com pixel")
    elif layout == "blob47":
        ms = list(mascaras) if mascaras else blob47_mascaras()
        if len(ms) != 47 or len(set(ms)) != 47:
            raise ValueError(f"o blob47 precisa de 47 máscaras distintas; vieram {len(set(ms))}")
        if any(reduzir_mascara(m) != m for m in ms):
            raise ValueError("há máscara com canto sem os dois lados vizinhos: não é uma máscara blob47 reduzida")
        if pular < 0 or pular + 47 > total:
            raise ValueError(f"layout 'blob47' precisa de 47 tiles a partir do slot {pular}; a folha tem {total} "
                             f"slots ({folha.colunas}×{folha.linhas}). Desenhe o conjunto completo ou use 'grid'.")
        slots = list(range(pular, pular + 47))
        terreno = dict(zip(slots, ms))
        vazios = [s for s in slots if s in folha.vazios]
        if vazios:
            avisos.append(f"{len(vazios)} tile(s) do blob47 estão vazios (slots {vazios[:8]}): o autotile vai "
                          f"pintar buraco nesses encaixes")
    else:
        raise ValueError(f"layout desconhecido: {layout!r} (use 'grid' ou 'blob47')")

    tw, th = folha.tile_w, folha.tile_h
    sub = "TileSetAtlasSource_1"
    out = [
        '[gd_resource type="TileSet" load_steps=3 format=3]',
        "",
        f'[ext_resource type="Texture2D" path="{textura}" id="1_atlas"]',
        "",
        f'[sub_resource type="TileSetAtlasSource" id="{sub}"]',
        'texture = ExtResource("1_atlas")',
    ]
    if folha.margem:
        out.append(f"margins = Vector2i({folha.margem}, {folha.margem})")
    if folha.espaco:
        out.append(f"separation = Vector2i({folha.espaco}, {folha.espaco})")
    out.append(f"texture_region_size = Vector2i({tw}, {th})")
    for s in slots:
        cx, cy = folha.coord(s)
        k = f"{cx}:{cy}/0"
        out.append(f"{k} = 0")
        if s in terreno:
            m = terreno[s]
            out.append(f"{k}/terrain_set = 0")
            out.append(f"{k}/terrain = 0")
            for bit, nome in PEERING_GODOT:
                if m & bit:
                    out.append(f"{k}/terrains_peering_bit/{nome} = 0")
    out += ["", "[resource]", f"tile_size = Vector2i({tw}, {th})"]
    if terreno:
        out += ["terrain_set_0/mode = 0",
                f'terrain_set_0/terrain_0/name = "{nome_terreno}"',
                f"terrain_set_0/terrain_0/color = {_cor_godot(cor_terreno)}"]
    out += [f'sources/0 = SubResource("{sub}")', ""]
    return ResultadoTres("\n".join(out), len(slots), terreno, avisos)


def guia_blob47(tile: int = 16, colunas: int = 8, cor=(90, 158, 75, 255), cor_vazio=(0, 0, 0, 0),
                mascaras: list[int] | None = None) -> np.ndarray:
    """Prancha-guia do blob47 na ordem canônica: em cada tile, o miolo e as bordas/cantos cheios da máscara.
    Serve de molde para desenhar o tileset à mão na mesma ordem que godot_tres espera."""
    ms = list(mascaras) if mascaras else blob47_mascaras()
    linhas = -(-len(ms) // colunas)
    img = np.zeros((linhas * tile, colunas * tile, 4), np.uint8)
    img[:] = cor_vazio
    b = max(1, tile // 4)
    for i, m in enumerate(ms):
        ox, oy = (i % colunas) * tile, (i // colunas) * tile
        t = img[oy:oy + tile, ox:ox + tile]
        t[b:tile - b, b:tile - b] = cor
        regioes = {N: (slice(0, b), slice(b, tile - b)), S: (slice(tile - b, tile), slice(b, tile - b)),
                   W: (slice(b, tile - b), slice(0, b)), E: (slice(b, tile - b), slice(tile - b, tile)),
                   NW: (slice(0, b), slice(0, b)), NE: (slice(0, b), slice(tile - b, tile)),
                   SW: (slice(tile - b, tile), slice(0, b)), SE: (slice(tile - b, tile), slice(tile - b, tile))}
        for bit, (ys, xs) in regioes.items():
            if m & bit:
                t[ys, xs] = cor
    return img
