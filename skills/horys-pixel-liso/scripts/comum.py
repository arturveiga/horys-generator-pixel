"""Funções comuns do motor (skill horys-pixel-liso).

Wrapper fino: reexporta horys_pixel.motor.comum (src/horys_pixel/motor/comum.py, no repo horys-generator-pixel), a fonte única
do motor. A config vem do config.json desta pasta (HORYS_MOTOR_CONFIG).
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

from horys_pixel.motor.comum import *  # noqa: E402,F401,F403
from horys_pixel.motor import comum as _m  # noqa: E402

globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})
