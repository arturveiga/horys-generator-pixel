"""Conceito -> .grade: converter, limpar e afinar (skill horys-pixel-liso).

Wrapper fino: o motor mora no pacote horys_pixel (src/horys_pixel/motor/conceito.py, no repo horys-generator-pixel), a fonte
única do motor (perfis 16/32/64, D01–D05, G01, prancha boas práticas + aprovados). Este script só roda
`python -m horys_pixel.motor.conceito` com o config.json desta pasta (HORYS_MOTOR_CONFIG). Ajuda e formato
completo: `python conceito.py -h` ou o topo de src/horys_pixel/motor/conceito.py.
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
# a config da skill (config.json ao lado) vale, a não ser que HORYS_MOTOR_CONFIG já aponte outra
os.environ.setdefault("HORYS_MOTOR_CONFIG", os.path.join(AQUI, "config.json"))
try:
    import horys_pixel  # noqa: F401  (pacote instalado, ex.: o .venv do repo)
except ImportError:  # a skill é junção para <repo>/skills/horys-pixel-liso: o pacote está em <repo>/src
    _SRC = os.path.normpath(os.path.join(os.path.realpath(AQUI), "..", "..", "..", "src"))
    if not os.path.isdir(os.path.join(_SRC, "horys_pixel")):
        sys.exit("horys-pixel-liso: pacote horys_pixel não achado (instale o repo horys-generator-pixel ou rode "
                 "com o python do .venv dele)")
    sys.path.insert(0, _SRC)
    os.environ["PYTHONPATH"] = _SRC + (os.pathsep + os.environ["PYTHONPATH"] if os.environ.get("PYTHONPATH") else "")

if __name__ == "__main__":
    import runpy
    runpy.run_module("horys_pixel.motor.conceito", run_name="__main__", alter_sys=True)
