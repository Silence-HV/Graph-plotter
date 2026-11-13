"""Kurvenanpassung (Fit) an Messdaten."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
from numpy.polynomial import Polynomial

FIT_KINDS = {
    "none": "Kein Fit",
    "linear": "Linear (a·x + b)",
    "poly2": "Polynom 2. Grades",
    "poly3": "Polynom 3. Grades",
    "exp": "Exponentiell (a·e^(b·x))",
}

_DEGREE = {"linear": 1, "poly2": 2, "poly3": 3}
_SUPERSCRIPT = {2: "²", 3: "³"}


@dataclass
class FitResult:
    kind: str
    coefficients: list[float]   # Polynom: aufsteigend (c0, c1, ...); exp: (a, b)
    r2: float
    equation: str
    predict: Callable[[np.ndarray], np.ndarray]


def _fmt(value: float) -> str:
    return f"{value:.4g}".replace("e+0", "e").replace("e-0", "e-").replace("e+", "e")


def _poly_equation(coeffs) -> str:
    terms = []
    for power in range(len(coeffs) - 1, -1, -1):
        c = coeffs[power]
        if c == 0:
            continue
        if power == 0:
            body = _fmt(abs(c))
        elif power == 1:
            body = f"{_fmt(abs(c))}·x"
        else:
            body = f"{_fmt(abs(c))}·x{_SUPERSCRIPT.get(power, '^' + str(power))}"
        sign = "−" if c < 0 else "+"
        terms.append((sign, body))
    if not terms:
        return "y = 0"
    first_sign, first_body = terms[0]
    text = ("−" if first_sign == "−" else "") + first_body
    for sign, body in terms[1:]:
        text += f" {sign} {body}"
    return "y = " + text


def _r_squared(y, y_pred) -> float:
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    if ss_tot == 0:
        return 1.0 if ss_res == 0 else float("nan")
    return 1.0 - ss_res / ss_tot


def fit_curve(x, y, kind: str) -> FitResult:
    """Kurve an (x, y) anpassen.

    Raises:
        ValueError: bei unbekannter Fit-Art, zu wenigen Punkten oder ungeeigneten Daten.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]

    if kind in _DEGREE:
        degree = _DEGREE[kind]
        if len(x) <= degree or len(np.unique(x)) <= degree:
            raise ValueError(f"mindestens {degree + 1} verschiedene X-Werte nötig")
        poly = Polynomial.fit(x, y, degree).convert()
        coeffs = [float(c) for c in poly.coef]
        coeffs += [0.0] * (degree + 1 - len(coeffs))
        return FitResult(kind, coeffs, _r_squared(y, poly(x)), _poly_equation(coeffs), poly)

    if kind == "exp":
        if len(x) < 2 or len(np.unique(x)) < 2:
            raise ValueError("mindestens 2 verschiedene X-Werte nötig")
        if np.any(y <= 0):
            raise ValueError("exponentieller Fit erfordert ausschließlich positive Y-Werte")
        line = Polynomial.fit(x, np.log(y), 1).convert()
        ln_a, b = (list(line.coef) + [0.0, 0.0])[:2]
        a = float(np.exp(ln_a))
        b = float(b)

        def predict(t, a=a, b=b):
            return a * np.exp(b * np.asarray(t, dtype=float))

        equation = f"y = {_fmt(a)}·e^({_fmt(b)}·x)"
        return FitResult(kind, [a, b], _r_squared(y, predict(x)), equation, predict)

    raise ValueError(f"Unbekannte Fit-Art: {kind}")
