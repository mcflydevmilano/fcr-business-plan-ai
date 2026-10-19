"""
charts.py - Grafici (matplotlib) usati sia nell'app (tema scuro) sia nei report PDF/Word (tema chiaro).
Ogni funzione restituisce una Figure; usa fig_png() per ottenere i byte PNG.
"""
import io
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from core import SOGLIE_DEFAULT, fmt_num, livello_classe  # noqa: E402

TEMI = {
    "dark": {"bg": "#0b0f19", "fg": "#e2e8f0", "grid": "#334155", "muted": "#94a3b8"},
    "light": {"bg": "#ffffff", "fg": "#0f172a", "grid": "#cbd5e1", "muted": "#64748b"},
}
SERIE = ["#2563eb", "#f59e0b", "#22c55e", "#a855f7", "#ef4444", "#06b6d4"]
VERDE, GIALLO, ROSSO = "#22c55e", "#f59e0b", "#ef4444"


def _t(tema):
    return TEMI.get(tema, TEMI["light"])


def _nuova(tema, w=7.2, h=3.6, ncols=1):
    t = _t(tema)
    fig, axes = plt.subplots(1, ncols, figsize=(w, h))
    fig.patch.set_facecolor(t["bg"])
    axs = axes if ncols > 1 else [axes]
    for ax in axs:
        ax.set_facecolor(t["bg"])
        ax.tick_params(colors=t["fg"], labelsize=8)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        for s in ("left", "bottom"):
            ax.spines[s].set_color(t["grid"])
        ax.grid(axis="y", color=t["grid"], alpha=0.5, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.title.set_color(t["fg"])
        ax.xaxis.label.set_color(t["fg"])
        ax.yaxis.label.set_color(t["fg"])
    return fig, axs


def _legenda(ax, tema, **kw):
    t = _t(tema)
    leg = ax.legend(frameon=False, fontsize=8, **kw)
    if leg:
        for txt in leg.get_texts():
            txt.set_color(t["fg"])


def _fin(x):
    """inf/None -> NaN (interrompe la linea invece di rompere il grafico)."""
    if x is None:
        return float("nan")
    return float("nan") if (isinstance(x, float) and math.isinf(x)) else x


def _k(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_num(v / 1000) + "k"))


def fig_png(fig, dpi=160):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return buf.getvalue()


# ----------------------------------------------------------------------------
def fig_pfn_ebitda(piani, soglie=None, covenant_max=None, tema="light", anno_base=None, base_val=None):
    """Andamento PFN/EBITDA. `piani`: {nome: lista righe del piano}. Mostra le soglie verde/giallo."""
    s = soglie or SOGLIE_DEFAULT
    fig, (ax,) = _nuova(tema)
    t = _t(tema)
    for i, (nome, piano) in enumerate(piani.items()):
        xs = [r["AnnoNum"] for r in piano]
        ys = [_fin(r["PFN/EBITDA"]) for r in piano]
        if anno_base is not None and base_val is not None and i == 0:
            xs, ys = [anno_base] + xs, [_fin(base_val)] + ys
        ax.plot(xs, ys, marker="o", linewidth=2, color=SERIE[i % len(SERIE)], label=nome)
        for x, y in zip(xs, ys):
            if not math.isnan(y):
                ax.annotate("0.0x" if abs(y) < 0.05 else f"{y:.1f}x", (x, y), textcoords="offset points", xytext=(0, 6),
                            ha="center", fontsize=7, color=t["fg"])
    ax.axhline(s["pfn_ebitda"][0], color=VERDE, linestyle="--", linewidth=1, label=f"Soglia verde ({s['pfn_ebitda'][0]:.1f}x)")
    ax.axhline(s["pfn_ebitda"][1], color=ROSSO, linestyle="--", linewidth=1, label=f"Soglia rossa ({s['pfn_ebitda'][1]:.1f}x)")
    if covenant_max is not None:
        ax.axhline(covenant_max, color=t["muted"], linestyle=":", linewidth=1.4, label=f"Covenant ({covenant_max:.1f}x)")
    ax.set_title("Andamento PFN / EBITDA", fontsize=10, loc="left")
    ax.set_ylabel("x", fontsize=8)
    ax.set_xticks(sorted({r["AnnoNum"] for p in piani.values() for r in p} | ({anno_base} if anno_base else set())))
    _legenda(ax, tema, loc="best")
    return fig


def fig_dscr(piano, soglie=None, covenant_min=None, tema="light"):
    s = soglie or SOGLIE_DEFAULT
    fig, (ax,) = _nuova(tema)
    t = _t(tema)
    xs = [r["AnnoNum"] for r in piano]
    vals = [r["DSCR"] if r["DSCR"] is not None else float("nan") for r in piano]
    colori = [
        VERDE if (not math.isnan(v) and v >= s["dscr"][0]) else (GIALLO if (not math.isnan(v) and v >= s["dscr"][1]) else ROSSO)
        for v in vals
    ]
    ax.bar([str(x) for x in xs], [0 if math.isnan(v) else v for v in vals], color=colori, width=0.55)
    for i, v in enumerate(vals):
        ax.text(i, (0 if math.isnan(v) else v) + 0.03, "n.d." if math.isnan(v) else f"{v:.2f}x",
                ha="center", fontsize=8, color=t["fg"])
    ax.axhline(s["dscr"][0], color=VERDE, linestyle="--", linewidth=1, label=f"Soglia verde ({s['dscr'][0]:.2f})")
    ax.axhline(s["dscr"][1], color=ROSSO, linestyle="--", linewidth=1, label=f"Soglia rossa ({s['dscr'][1]:.2f})")
    if covenant_min is not None:
        ax.axhline(covenant_min, color=t["muted"], linestyle=":", linewidth=1.4, label=f"Covenant ({covenant_min:.2f})")
    vmax = max([v for v in vals if not math.isnan(v)] + [s["dscr"][0], covenant_min or 0])
    ax.set_ylim(0, vmax * 1.45)
    ax.set_title("DSCR per anno", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper center", ncol=3)
    return fig


def fig_confronto(risultati, soglie=None, tema="light"):
    """Confronto scenari: PFN/EBITDA a fine piano e punteggio di scoring. `risultati`: {nome: esegui_scenario()}"""
    s = soglie or SOGLIE_DEFAULT
    fig, (a1, a2) = _nuova(tema, w=7.6, h=3.4, ncols=2)
    t = _t(tema)
    nomi = list(risultati.keys())
    lev = [_fin(risultati[n]["piano"][-1]["PFN/EBITDA"]) for n in nomi]
    a1.bar(nomi, [0 if math.isnan(v) else v for v in lev], color=[SERIE[i % len(SERIE)] for i in range(len(nomi))], width=0.55)
    for i, v in enumerate(lev):
        a1.text(i, (0 if math.isnan(v) else v) + 0.05, "n.s." if math.isnan(v) else f"{v:.2f}x", ha="center", fontsize=8, color=t["fg"])
    a1.axhline(s["pfn_ebitda"][0], color=VERDE, linestyle="--", linewidth=1)
    a1.axhline(s["pfn_ebitda"][1], color=ROSSO, linestyle="--", linewidth=1)
    a1.set_title("PFN / EBITDA a fine piano", fontsize=10, loc="left")

    pt = [risultati[n]["rating"]["punti"] for n in nomi]
    col = [{2: VERDE, 1: GIALLO, 0: ROSSO}[livello_classe(risultati[n]["rating"]["classe"])] for n in nomi]
    a2.bar(nomi, pt, color=col, width=0.55)
    for i, v in enumerate(pt):
        a2.text(i, v + 0.1, f"{v}/8", ha="center", fontsize=8, color=t["fg"])
    a2.set_ylim(0, 9)
    a2.set_title("Punteggio di scoring", fontsize=10, loc="left")
    for ax in (a1, a2):
        ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    return fig


def fig_cascata(piano, pfn0, tema="light"):
    """Cascata: dalla PFN iniziale alla PFN finale, cumulando le componenti del free cash flow."""
    t = _t(tema)
    fig, (ax,) = _nuova(tema, w=7.6, h=3.8)
    somma = lambda k: sum(r[k] for r in piano)  # noqa: E731
    passi = [
        ("EBITDA", -somma("EBITDA")),
        ("Imposte", somma("Imposte")),
        ("Capex", somma("Capex")),
        ("Interessi", somma("Interessi")),
        ("Var. CCN", somma("dCCN")),
    ]
    pfn_fin = piano[-1]["PFN"]
    etichette, bottoms, altezze, colori = ["PFN iniziale"], [0], [pfn0], [SERIE[0]]
    corrente = pfn0
    for nome, delta in passi:
        etichette.append(nome)
        bottoms.append(corrente if delta >= 0 else corrente + delta)
        altezze.append(abs(delta))
        colori.append(ROSSO if delta > 0 else VERDE)   # aumenta il debito = rosso
        corrente += delta
    etichette.append("PFN finale")
    bottoms.append(0)
    altezze.append(pfn_fin)
    colori.append(SERIE[0])
    for i, (b, h, c) in enumerate(zip(bottoms, altezze, colori)):
        ax.bar(i, h, bottom=b, color=c, width=0.6)
    for i, nome in enumerate(etichette):
        if 0 < i < len(etichette) - 1:
            delta = passi[i - 1][1]
            ax.text(i, bottoms[i] + altezze[i] + abs(max(altezze)) * 0.02, f"{'+' if delta > 0 else '-'}{fmt_num(abs(delta) / 1000)}k",
                    ha="center", fontsize=7, color=t["fg"])
    ax.text(0, pfn0, f" {fmt_num(pfn0 / 1000)}k", ha="center", va="bottom", fontsize=7, color=t["fg"])
    ax.text(len(etichette) - 1, max(pfn_fin, 0), f" {fmt_num(pfn_fin / 1000)}k", ha="center", va="bottom", fontsize=7, color=t["fg"])
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set_xticks(range(len(etichette)))
    ax.set_xticklabels(etichette, fontsize=8)
    _k(ax)
    ax.set_title(f"Dalla PFN iniziale alla PFN finale (cumulato {len(piano)} anni, EUR)", fontsize=10, loc="left")
    return fig


def fig_storico(storico, dati, piano, tema="light"):
    """Ricavi ed EBITDA: storico, anno base e proiezione."""
    t = _t(tema)
    fig, (ax,) = _nuova(tema, w=7.6, h=3.6)
    anni = [r["anno"] for r in storico] + [int(dati["anno_riferimento"])] + [r["AnnoNum"] for r in piano]
    ricavi = [r["ricavi"] for r in storico] + [dati["ricavi"]] + [r["Ricavi"] for r in piano]
    ebitda = [r["ebitda"] for r in storico] + [dati["ebitda"]] + [r["EBITDA"] for r in piano]
    n_st, n_pr = len(storico), len(piano)
    hatch = [""] * (n_st + 1) + ["//"] * n_pr
    x = list(range(len(anni)))
    w = 0.38
    for i in x:
        ax.bar(i - w / 2, ricavi[i], width=w, color=SERIE[0], hatch=hatch[i], edgecolor=t["bg"], label="Ricavi" if i == 0 else None)
        ax.bar(i + w / 2, ebitda[i], width=w, color=SERIE[2], hatch=hatch[i], edgecolor=t["bg"], label="EBITDA" if i == 0 else None)
    ax.set_xticks(x)
    ax.set_xticklabels([str(a) + ("*" if i > n_st else "") for i, a in enumerate(anni)], fontsize=8)
    _k(ax)
    ax.set_title("Ricavi ed EBITDA: storico, anno base e proiezione (* = proiezione)", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper left")
    return fig


def fig_commesse(per_cliente, tema="light", top=8):
    t = _t(tema)
    fig, (ax,) = _nuova(tema, w=7.2, h=3.4)
    d = per_cliente.head(top)
    ax.bar(d["Cliente"], d["Importo"], color=SERIE[0], width=0.55, label="Importo commesse")
    ax.bar(d["Cliente"], d["Backlog"], color=SERIE[1], width=0.3, label="Backlog residuo")
    for i, q in enumerate(d["Quota_pct"]):
        ax.text(i, d["Importo"].iloc[i], f"{q:.0f}%", ha="center", va="bottom", fontsize=8, color=t["fg"])
    ax.tick_params(axis="x", rotation=20)
    _k(ax)
    ax.set_title("Portafoglio per cliente (% sul totale importo)", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper right")
    return fig


# ----------------------------------------------------------------------------
# Business Plan Studio
# ----------------------------------------------------------------------------
def fig_bp_economico(anni, tema="light"):
    """Ricavi, EBITDA e utile netto per anno (barre affiancate)."""
    fig, (ax,) = _nuova(tema)
    t = _t(tema)
    xs = list(range(len(anni)))
    w = 0.26
    serie = [("Ricavi", "Ricavi", SERIE[0]), ("EBITDA", "EBITDA", SERIE[2]), ("Utile netto", "Utile netto", SERIE[1])]
    for i, (chiave, nome, col) in enumerate(serie):
        vals = [r[chiave] for r in anni]
        ax.bar([x + (i - 1) * w for x in xs], vals, width=w, color=col, label=nome)
        for x, v in zip(xs, vals):
            ax.text(x + (i - 1) * w, v + (abs(v) * 0.02 if v >= 0 else -abs(v) * 0.02), f"{fmt_num(v / 1000)}k", ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=6.5, color=t["fg"])
    ax.axhline(0, color=t["grid"], linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(r["AnnoNum"]) for r in anni])
    _k(ax)
    ax.set_title("Ricavi, EBITDA e utile netto", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper left")
    return fig


def fig_bp_finanza(anni, cassa0=0.0, tema="light"):
    """Cassa di fine anno (verde/rosso) e PFN (linea)."""
    fig, (ax,) = _nuova(tema)
    t = _t(tema)
    etich = ["Avvio"] + [str(r["AnnoNum"]) for r in anni]
    cassa = [cassa0] + [r["Cassa finale"] for r in anni]
    pfn = [None] + [r["PFN"] for r in anni]
    ax.bar(etich, cassa, color=[VERDE if v >= 0 else ROSSO for v in cassa], width=0.5, label="Cassa di fine anno")
    for i, v in enumerate(cassa):
        ax.text(i, v + (abs(v) * 0.03 if v >= 0 else -abs(v) * 0.03), f"{fmt_num(v / 1000)}k", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=7, color=t["fg"])
    xs = [i for i, v in enumerate(pfn) if v is not None]
    ax.plot(xs, [pfn[i] for i in xs], color=SERIE[0], marker="o", linewidth=2, label="PFN (debito - cassa)")
    ax.axhline(0, color=t["grid"], linewidth=0.8)
    _k(ax)
    ax.set_title("Cassa e posizione finanziaria netta", fontsize=10, loc="left")
    _legenda(ax, tema, loc="best")
    return fig


def fig_bp_mutuo(mutuo, tema="light"):
    """Piano di ammortamento: quota capitale + interessi per anno e debito residuo."""
    fig, (ax,) = _nuova(tema)
    xs = [str(r["Anno"]) for r in mutuo]
    cap = [r["Quota capitale"] for r in mutuo]
    inte = [r["Interessi"] for r in mutuo]
    ax.bar(xs, cap, color=SERIE[0], width=0.55, label="Quota capitale")
    ax.bar(xs, inte, bottom=cap, color=SERIE[1], width=0.55, label="Interessi")
    ax2 = ax.twinx()
    ax2.plot(xs, [r["Debito residuo"] for r in mutuo], color=SERIE[4], marker="o", linewidth=1.8, label="Debito residuo")
    for a in (ax, ax2):
        _k(a)
        a.tick_params(colors=_t(tema)["fg"], labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_color(_t(tema)["grid"])
    ax.set_ylim(0, max([c + i for c, i in zip(cap, inte)] + [1]) * 1.4)
    ax2.set_ylim(0, max([r["Debito residuo"] for r in mutuo] + [1]) * 1.4)
    ax.set_xlabel("Anno del finanziamento", fontsize=8)
    ax.set_title("Piano di ammortamento del finanziamento", fontsize=10, loc="left")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    leg = ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8, loc="upper center", ncol=3)
    for txt in leg.get_texts():
        txt.set_color(_t(tema)["fg"])
    return fig


def fig_bp_scenari(risultati, tema="light"):
    """Confronto tra scenari: cassa di fine anno per ciascuno (linee) e DSCR minimo nel titolo delle legende."""
    fig, (ax,) = _nuova(tema)
    t = _t(tema)
    colori = {"Pessimistico": ROSSO, "Base": SERIE[0], "Ottimistico": VERDE}
    for i, (nome, o) in enumerate(risultati.items()):
        xs = ["Avvio"] + [str(r["AnnoNum"]) for r in o["anni"]]
        ys = [o["kpi"]["cassa_iniziale"]] + [r["Cassa finale"] for r in o["anni"]]
        d = o["kpi"]["dscr_min"]
        etich = f"{nome}" + (f" (DSCR min {d:.2f}x)".replace(".", ",") if d is not None else "")
        ax.plot(xs, ys, marker="o", linewidth=2, color=colori.get(nome, SERIE[(i + 3) % len(SERIE)]), label=etich)
    ax.axhline(0, color=t["grid"], linewidth=0.9)
    _k(ax)
    ax.set_title("Cassa di fine anno nei tre scenari", fontsize=10, loc="left")
    _legenda(ax, tema, loc="best")
    return fig


def fig_tornado(righe, etichetta_metrica, tema="light", max_righe=8):
    """Grafico 'tornado': scostamento della metrica rispetto alla base per ogni variabile."""
    fig, (ax,) = _nuova(tema, h=3.8)
    t = _t(tema)
    righe = list(righe)[:max_righe][::-1]
    if not righe:
        return fig
    base = righe[0]["Base"]
    for i, r in enumerate(righe):
        lo, hi = r["Con valore minore"] - base, r["Con valore maggiore"] - base
        ax.barh(i, lo, color=ROSSO if lo < 0 else VERDE, height=0.55, alpha=0.9)
        ax.barh(i, hi, color=VERDE if hi > 0 else ROSSO, height=0.55, alpha=0.9)
    ax.set_yticks(range(len(righe)))
    ax.set_yticklabels([f"{r['Variabile']} ({r['Variazione']})" for r in righe], fontsize=8, color=t["fg"])
    ax.axvline(0, color=t["fg"], linewidth=0.9)
    ax.grid(axis="x", color=t["grid"], alpha=0.5, linewidth=0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(f"Scostamento di {etichetta_metrica} rispetto al caso base ({fmt_num(base, 2) if abs(base) < 100 else fmt_num(base)})", fontsize=8)
    ax.set_title("Sensibilita': quali ipotesi pesano di piu'", fontsize=10, loc="left")
    return fig
