"""Malha 3D a partir da ficha, local e gratuito (Hunyuan3D-2, Tencent Hunyuan 3D 2.0 Community License).

    ~/.horys-pixel/venv-hy3d/Scripts/python.exe gerar_malha_hy3d.py --modo mini     # só a frente
    ~/.horys-pixel/venv-hy3d/Scripts/python.exe gerar_malha_hy3d.py --modo mv       # frente + lado + costas

Entradas: ../referencia/entrada_3d/{frente,lado,costas}.png (RGBA, fundo transparente).
Saída: ../blender/hy3d_<modo>.glb (só forma; cor e materiais são feitos depois no Blender).
Roda só na GPU local; os pesos ficam no cache do Hugging Face do usuário. Nada é enviado para fora.
"""
import argparse
import time
from pathlib import Path

import torch
from PIL import Image

AQUI = Path(__file__).resolve().parent
ENTRADA = AQUI.parent / "referencia" / "entrada_3d"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["mini", "mv"], default="mini")
    ap.add_argument("--passos", type=int, default=30)
    ap.add_argument("--octree", type=int, default=256)
    ap.add_argument("--semente", type=int, default=7)
    a = ap.parse_args()
    from hy3dgen.shapegen import FaceReducer, FloaterRemover, DegenerateFaceRemover, \
        Hunyuan3DDiTFlowMatchingPipeline
    t0 = time.time()
    if a.modo == "mini":
        pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            "tencent/Hunyuan3D-2mini", subfolder="hunyuan3d-dit-v2-mini", use_safetensors=True, device="cuda")
        imagem = Image.open(ENTRADA / "frente.png").convert("RGBA")
    else:
        pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
            "tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv", use_safetensors=True, device="cuda")
        imagem = {"front": Image.open(ENTRADA / "frente.png").convert("RGBA"),
                  "left": Image.open(ENTRADA / "lado.png").convert("RGBA"),
                  "back": Image.open(ENTRADA / "costas.png").convert("RGBA")}
    print(f"[hy3d] modelo carregado em {time.time() - t0:.0f} s; VRAM {torch.cuda.memory_allocated() / 2**30:.1f} GB")
    t1 = time.time()
    g = torch.manual_seed(a.semente)
    malha = pipe(image=imagem, num_inference_steps=a.passos, octree_resolution=a.octree, num_chunks=20000,
                 generator=g, output_type="trimesh")[0]
    malha = FloaterRemover()(malha)
    malha = DegenerateFaceRemover()(malha)
    malha = FaceReducer()(malha, max_facenum=60000)
    saida = AQUI / f"hy3d_{a.modo}.glb"
    malha.export(saida)
    print(f"[hy3d] {saida.name}: {len(malha.vertices)} vértices, {len(malha.faces)} faces, {time.time() - t1:.0f} s; "
          f"pico de VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GB")


if __name__ == "__main__":
    main()
