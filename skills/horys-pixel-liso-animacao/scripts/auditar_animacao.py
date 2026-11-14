"""Read-only structural audit. Requires Pillow and numpy; no beauty/pass score."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageSequence


def load_frames(path):
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = data["frames"]
        if not isinstance(entries, list):
            raise ValueError("Exporte Aseprite com --format json-array")
        sheet_path = path.parent / Path(data["meta"]["image"]).name
        sheet = Image.open(sheet_path).convert("RGBA")
        frames, times = [], []
        for entry in entries:
            if entry.get("rotated") or entry.get("trimmed"):
                raise ValueError("Exporte sem rotated/trimmed para comparar canvas e pivo")
            b = entry["frame"]
            frames.append(sheet.crop((b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"])))
            times.append(entry["duration"])
        return frames, times, sheet_path
    im = Image.open(path)
    frames, times = [], []
    for fr in ImageSequence.Iterator(im):
        frames.append(fr.convert("RGBA"))
        times.append(fr.info.get("duration", 0))
    return frames, times, path


def audit(path):
    frames, times, image_path = load_frames(path)
    if not frames or len(set(fr.size for fr in frames)) != 1:
        raise ValueError("Nenhum quadro ou canvas variavel")
    arrays = [np.asarray(fr).copy() for fr in frames]
    for ar in arrays:
        ar[ar[:, :, 3] == 0] = 0  # Ignore invisible RGB garbage.
    hashes = [hashlib.sha256(ar.tobytes()).hexdigest() for ar in arrays]
    masks = [ar[:, :, 3] > 0 for ar in arrays]
    all_colors = set()
    bounds, areas, border, partial, diffs = [], [], [], [], []
    for i, (ar, mask) in enumerate(zip(arrays, masks)):
        ys, xs = np.where(mask)
        bounds.append([int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None)
        areas.append(int(mask.sum()))
        border.append(bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any()))
        partial.append(int(((ar[:, :, 3] > 0) & (ar[:, :, 3] < 255)).sum()))
        all_colors.update(map(tuple, ar[ar[:, :, 3] == 255, :3].tolist()))
        nxt = (i + 1) % len(arrays)
        union = mask | masks[nxt]
        changed = np.any(ar != arrays[nxt], axis=2) & union
        diffs.append(round(float(changed.sum() / max(1, union.sum())), 5))
    med = float(np.median(diffs[:-1])) if len(diffs) > 1 else 0.0
    duplicates = [[i + 1, j + 1] for i in range(len(hashes)) for j in range(i + 1, len(hashes)) if hashes[i] == hashes[j]]
    warnings = []
    if any(border): warnings.append("pixels_na_borda")
    if any(partial): warnings.append("alpha_parcial")
    if duplicates: warnings.append("quadros_identicos")
    if not all(isinstance(t, (int, float)) and t > 0 for t in times): warnings.append("duracao_ausente_ou_invalida")
    if med and diffs[-1] > med * 1.5: warnings.append("costura_acima_de_1_5x_mediana_triagem")
    return {
        "tipo": "triagem_estrutural_nao_e_aprovacao_visual",
        "entrada": str(path.resolve()), "imagem": str(image_path.resolve()),
        "sha256_entrada": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sha256_imagem": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        "quadros": len(frames), "desenhos_unicos": len(set(hashes)),
        "canvas": list(frames[0].size), "duracoes_ms": times, "total_ms": sum(times),
        "cores_opacas": len(all_colors), "alpha_parcial_por_quadro": partial,
        "bbox_por_quadro": bounds, "area_por_quadro": areas, "toca_borda": border,
        "pares_duplicados_1_based": duplicates, "mudanca_por_transicao": diffs,
        "costura_sobre_mediana": round(diffs[-1] / med, 4) if med else None,
        "sha256_quadros": hashes, "avisos": warnings,
        "limites": "Nao mede beleza, identidade, apoio dos pes, overlap ou redesenho. Escala/paleta/fps precisam de contrato proprio."
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--palette", type=Path, help="Paleta GPL esperada; valida RGB, nao so contagem")
    parser.add_argument("--expected-frames", type=int)
    parser.add_argument("--expected-total-ms", type=int)
    args = parser.parse_args()
    result = audit(args.input)
    result["paleta_conferida"] = False
    if args.palette:
        expected = set()
        for line in args.palette.read_text(encoding="utf-8-sig").splitlines():
            parts = line.split()
            if len(parts) >= 3 and all(p.isdigit() for p in parts[:3]):
                expected.add(tuple(map(int, parts[:3])))
        if not expected:
            raise ValueError("Paleta GPL sem cores")
        frames, _, _ = load_frames(args.input)
        actual = set()
        for frame in frames:
            ar = np.asarray(frame)
            actual.update(map(tuple, ar[ar[:, :, 3] == 255, :3].tolist()))
        unexpected = sorted(actual - expected)
        result["paleta_conferida"] = str(args.palette.resolve())
        result["cores_fora_da_paleta"] = unexpected
        if unexpected:
            result["avisos"].append("cores_fora_da_paleta")
    if args.expected_frames is not None and result["quadros"] != args.expected_frames:
        result["avisos"].append("contagem_diverge_do_contrato")
    if args.expected_total_ms is not None and result["total_ms"] != args.expected_total_ms:
        result["avisos"].append("duracao_diverge_do_contrato")
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
