# -*- coding: utf-8 -*-
"""Genera las figuras del informe a partir de los registros de las corridas.

Lee los CSV de ../../logs/ (uno por corrida, una fila por ciclo del lazo) y
escribe en figuras/ los gráficos en PDF. Se corre desde esta carpeta:

    python generar_figuras.py

Las corridas usadas son del 2026-10-02, ya con el ultrasónico:
  - corrida_20261002_104127: aproximación al objetivo (56,6 a 58,8 s).
  - corrida_20261002_103658: huida hacia una pared, umbral de esquive 20 cm.
  - corrida_20261002_105908: huida hacia una pared, umbral de esquive 30 cm.
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

AQUI = os.path.dirname(os.path.abspath(__file__))
LOGS = os.path.join(AQUI, "..", "..", "logs")
SALIDA = os.path.join(AQUI, "figuras")

AZUL, NARANJA, GRIS, ROJO, VERDE = "#2A78D6", "#EB6834", "#52514E", "#D03B3B", "#0CA30C"

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "legend.fontsize": 7, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "grid.linewidth": 0.5,
    "pdf.fonttype": 42, "font.family": "DejaVu Sans",
})


def leer(nombre):
    ruta = os.path.join(LOGS, nombre)
    filas = [l for l in open(ruta, encoding="utf-8") if not l.startswith("#")]
    return list(csv.DictReader(filas))


def col(filas, clave):
    """La columna como números; None donde no hay dato."""
    salida = []
    for f in filas:
        try:
            salida.append(float(f[clave]))
        except (KeyError, ValueError):
            salida.append(None)
    return salida


def tramo(filas, t0, t1):
    return [f for f in filas if t0 <= float(f["t_s"]) <= t1]


def guardar(fig, nombre):
    os.makedirs(SALIDA, exist_ok=True)
    fig.savefig(os.path.join(SALIDA, nombre), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print("figura:", nombre)


# ------------------------------------------------------------------ 1. FPS
def fig_fps():
    tam = ["640", "480", "320", "256"]
    fps = [3.20, 5.17, 11.33, 17.7]
    fig, ax = plt.subplots(figsize=(3.4, 2.1))
    barras = ax.bar(tam, fps, color=[GRIS, GRIS, AZUL, GRIS], width=0.62)
    for b, v in zip(barras, fps):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.35, ("%.1f" % v).replace(".", ","),
                ha="center", va="bottom", fontsize=7.5)
    ax.axhline(5.0, color=ROJO, linestyle="--", linewidth=1)
    ax.text(-0.45, 6.1, "mínimo aceptable: 5", color=ROJO, ha="left", fontsize=7)
    ax.set_xlabel("tamaño de la imagen de inferencia (px)")
    ax.set_ylabel("imágenes por segundo")
    ax.set_ylim(0, 20.5)
    ax.grid(axis="x", visible=False)
    guardar(fig, "fig_fps.pdf")


# --------------------------------------------------------- 2. aproximación
def fig_aproximacion():
    filas = tramo(leer("corrida_20261002_104127.csv"), 56.0, 59.6)
    t0 = 56.651                      # instante en que confirma el objetivo
    t = [float(f["t_s"]) - t0 for f in filas]
    ex, ar = col(filas, "obj_ex"), col(filas, "obj_ar")
    vl, va, d = col(filas, "v_lin"), col(filas, "v_ang"), col(filas, "dist_cm")
    t_enc = 58.782 - t0

    fig, ejes = plt.subplots(3, 1, figsize=(4.9, 4.3), sharex=True,
                             gridspec_kw={"hspace": 0.16})
    a = ejes[0]
    a.plot(t, ex, color=AZUL, marker="o", markersize=2.2, linewidth=1.1, label="error lateral $e_x$")
    a.axhspan(-0.08, 0.08, color=AZUL, alpha=0.10, linewidth=0)
    a.set_ylabel("$e_x$")
    a.set_ylim(-0.45, 0.8)
    b = a.twinx()
    b.spines["right"].set_visible(True)
    b.plot(t, ar, color=NARANJA, marker="s", markersize=2.2, linewidth=1.1, label="área relativa $a$")
    b.axhline(0.35, color=NARANJA, linestyle="--", linewidth=0.8)
    b.text(-0.55, 0.365, "$a_{obj}$ = 0,35", color=NARANJA, fontsize=7)
    b.set_ylabel("$a$")
    b.set_ylim(0, 0.62)
    b.grid(False)
    lineas = a.get_lines()[:1] + b.get_lines()[:1]
    a.legend(lineas, [l.get_label() for l in lineas], loc="lower center", ncol=2,
             frameon=False, bbox_to_anchor=(0.5, 1.10))

    a = ejes[1]
    a.step(t, vl, where="post", color=GRIS, linewidth=1.2, label="$v_{lin}$")
    a.step(t, va, where="post", color=VERDE, linewidth=1.2, label="$v_{ang}$")
    a.set_ylabel("comando (0 a 100)")
    a.set_ylim(-15, 62)
    a.legend(loc="upper right", ncol=2, frameon=False)

    a = ejes[2]
    a.plot(t, d, color=ROJO, marker="^", markersize=2.2, linewidth=1.1)
    a.set_ylabel("ultrasónico (cm)")
    a.set_xlabel("tiempo desde que confirma el objetivo (s)")
    a.set_ylim(0, 130)

    for a in ejes:
        a.axvline(0, color="k", linewidth=0.6, linestyle=":")
        a.axvline(t_enc, color="k", linewidth=0.6, linestyle=":")
    arriba = ejes[0].get_xaxis_transform()
    ejes[0].text(0, 1.03, "confirma", fontsize=7, ha="center", transform=arriba)
    ejes[0].text(t_enc, 1.03, "frena", fontsize=7, ha="center", transform=arriba)
    guardar(fig, "fig_aproximacion.pdf")


# ---------------------------------------------------------------- 3. huida
def panel_huida(ax, nombre, t0, t1, umbral, titulo):
    filas = tramo(leer(nombre), t0, t1)
    t = [float(f["t_s"]) - t0 for f in filas]
    d = col(filas, "dist_cm")
    fases = {"fase 1": ("#F6D8CC", "1: retrocede"), "fase 2": ("#F2B79F", "2: gira"),
             "fase 3: avance": ("#D9E8FA", "3: avanza"),
             "fase 3: obst": ("#F9C8C8", "3: esquiva")}
    usados = set()
    for i, f in enumerate(filas):
        for clave, (color, etiqueta) in fases.items():
            if f["motivo"].startswith(clave):
                fin = t[i + 1] if i + 1 < len(t) else t[i] + 0.09
                ax.axvspan(t[i], fin, color=color, linewidth=0,
                           label=etiqueta if etiqueta not in usados else None)
                usados.add(etiqueta)
    ax.plot(t, [min(x, 200) if x is not None else None for x in d], color=GRIS,
            marker="o", markersize=2.0, linewidth=1.0)
    ax.axhline(umbral, color=ROJO, linestyle="--", linewidth=0.9)
    ax.text(t[0] + 0.05, umbral + 5, "umbral de esquive: %d cm" % umbral, color=ROJO,
            ha="left", fontsize=7)
    ax.set_ylim(0, 205)
    ax.set_title(titulo, loc="left")
    ax.set_xlabel("tiempo desde que decide huir (s)")
    ax.grid(axis="x", visible=False)


def fig_huida():
    fig, ejes = plt.subplots(1, 2, figsize=(6.9, 2.5), sharey=True,
                             gridspec_kw={"wspace": 0.06})
    panel_huida(ejes[0], "corrida_20261002_103658.csv", 0.309, 5.60, 20,
                "(a) un solo umbral, de 20 cm")
    panel_huida(ejes[1], "corrida_20261002_105908.csv", 12.388, 17.70, 30,
                "(b) umbral de esquive de 30 cm")
    ejes[0].set_ylabel("lectura del ultrasónico (cm)")
    manijas, etiquetas = ejes[0].get_legend_handles_labels()
    fig.legend(manijas, etiquetas, loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, -0.13))
    guardar(fig, "fig_huida.pdf")


if __name__ == "__main__":
    fig_fps()
    fig_aproximacion()
    fig_huida()
