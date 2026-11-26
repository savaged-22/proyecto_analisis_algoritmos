"""Los colores de la interfaz cumplen WCAG AA: texto 4.5:1; controles, bordes que informan y foco 3:1.

Lee los tokens de src/ui/static/estilos/tokens.css (paleta y usos) y calcula el contraste de cada par
que la interfaz pone uno sobre otro.
"""

import re
import unittest
from pathlib import Path

TOKENS = Path(__file__).resolve().parent.parent / "src" / "ui" / "static" / "estilos" / "tokens.css"

# (color, fondo, mínimo)
PAIRS = [
    ("--texto", "--superficie", 4.5),
    ("--texto", "--fondo", 4.5),
    ("--texto", "--seleccion", 4.5),
    ("--texto", "--superficie-hundida", 4.5),
    ("--texto-suave", "--superficie", 4.5),
    ("--texto-suave", "--fondo", 4.5),
    ("--texto-tenue", "--superficie", 4.5),
    ("--texto-tenue", "--fondo", 4.5),
    ("--acento", "--superficie", 4.5),
    ("--acento", "--seleccion", 4.5),
    ("--sobre-acento", "--acento", 4.5),
    ("--sobre-acento", "--acento-fuerte", 4.5),
    ("--exito", "--exito-fondo", 4.5),
    ("--exito", "--superficie", 4.5),
    ("--aviso", "--aviso-fondo", 4.5),
    ("--aviso", "--fondo", 4.5),
    ("--peligro", "--peligro-fondo", 4.5),
    ("--peligro", "--superficie", 4.5),
    ("--info", "--info-fondo", 4.5),
    ("--borde-fuerte", "--superficie", 3.0),
    ("--foco", "--superficie", 3.0),
    ("--foco", "--fondo", 3.0),
    ("--marca", "--seleccion", 3.0),
]


def read_tokens() -> dict[str, str]:
    text = TOKENS.read_text(encoding="utf-8")
    root = text[text.index(":root"):text.index("}", text.index(":root"))]
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", root))


def resolve(tokens: dict[str, str], name: str) -> str:
    value = tokens[name].strip()
    while value.startswith("var("):
        value = tokens[value[4:-1].strip()].strip()
    return value


def luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class ContrastTest(unittest.TestCase):
    def test_contrast_formula(self) -> None:
        self.assertAlmostEqual(contrast("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(contrast("#ffffff", "#ffffff"), 1.0)

    def test_pairs_meet_wcag_aa(self) -> None:
        tokens = read_tokens()
        for fg, bg, minimum in PAIRS:
            with self.subTest(color=fg, fondo=bg):
                ratio = contrast(resolve(tokens, fg), resolve(tokens, bg))
                self.assertGreaterEqual(ratio, minimum, f"{fg} sobre {bg}: {ratio:.2f}:1 (mínimo {minimum}:1)")


if __name__ == "__main__":
    unittest.main()
