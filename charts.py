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


# ----------------------------------------------------------------------------
# CASH FLOW DI CANTIERE E PREVENTIVO
# ----------------------------------------------------------------------------
def fig_cf_mensile(mesi, fido=None, tema="light"):
    """Incassi (barre verdi, in alto), pagamenti e costi generali (barre rosse, in basso) e cassa finale (linea)."""
    fig, (ax,) = _nuova(tema, w=7.6, h=4.2)
    t = _t(tema)
    xs = [r["Mese"] for r in mesi]
    ax.bar(xs, [r["Incassi"] for r in mesi], color=VERDE, width=0.62, label="Incassi")
    ax.bar(xs, [-(r["Pagamenti"] + r["Costi generali"]) for r in mesi], color=ROSSO, width=0.62, alpha=0.85, label="Pagamenti e costi generali")
    ax.plot(xs, [r["Cassa finale"] for r in mesi], color=SERIE[0], marker="o", markersize=3.5, linewidth=2, label="Cassa di fine mese")
    if fido:
        ax.axhline(-fido, color=GIALLO, linestyle="--", linewidth=1.3, label=f"Limite del fido ({fmt_num(fido / 1000)}k)")
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set_xticks(xs if len(xs) <= 24 else xs[::2])
    ax.set_xlabel("Mese", fontsize=8)
    _k(ax)
    ax.set_title("Incassi, pagamenti e cassa mese per mese", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4)
    return fig


def fig_cf_stress(risultati, fido=None, tema="light"):
    """Cassa di fine mese nei diversi casi di stress."""
    fig, (ax,) = _nuova(tema, w=7.6, h=4.8)
    t = _t(tema)
    for i, (nome, o) in enumerate(risultati.items()):
        xs = [r["Mese"] for r in o["mesi"]]
        ax.plot(xs, [r["Cassa finale"] for r in o["mesi"]], linewidth=2.4 if i == 0 else 1.5, color=SERIE[i % len(SERIE)], label=nome,
                linestyle="-" if i == 0 else "--")
    if fido:
        ax.axhline(-fido, color=GIALLO, linestyle=":", linewidth=1.4, label="Limite del fido")
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set_xlabel("Mese", fontsize=8)
    _k(ax)
    ax.set_title("Cassa di fine mese: caso base e stress test", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    return fig


def fig_cf_crediti(mesi, tema="light"):
    """Crediti netti verso clienti e debiti verso fornitori nel tempo (esposizione del capitale circolante)."""
    fig, (ax,) = _nuova(tema, w=7.6, h=3.2)
    xs = [r["Mese"] for r in mesi]
    ax.fill_between(xs, [r["Crediti netti"] for r in mesi], color=SERIE[1], alpha=0.35, label="Crediti netti verso clienti")
    ax.plot(xs, [r["Crediti netti"] for r in mesi], color=SERIE[1], linewidth=2)
    ax.fill_between(xs, [r["Debiti fornitori"] for r in mesi], color=SERIE[3], alpha=0.25, label="Debiti verso fornitori")
    ax.plot(xs, [r["Debiti fornitori"] for r in mesi], color=SERIE[3], linewidth=2)
    ax.axhline(0, color=_t(tema)["fg"], linewidth=0.8)
    ax.set_xlabel("Mese", fontsize=8)
    _k(ax)
    ax.set_title("Crediti e debiti di cantiere (capitale circolante)", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper left")
    return fig


def fig_pv_composizione(k, tema="light"):
    """Da dove nasce il prezzo: costi diretti, spese generali, utile, oneri di sicurezza (e sconto concesso)."""
    fig, (ax,) = _nuova(tema, w=7.6, h=2.4)
    t = _t(tema)
    parti = [("Costi diretti", k["costi_diretti"], SERIE[0]), ("Spese generali", k["spese_generali"], SERIE[3]),
             ("Utile", max(0.0, k["utile"]), VERDE), ("Oneri sicurezza", k["oneri_sicurezza"], SERIE[1])]
    tot = sum(v for _, v, _ in parti) or 1.0
    sx = 0.0
    for nome, v, col in parti:
        ax.barh(0, v, left=sx, color=col, height=0.5, label=f"{nome} ({fmt_num(v / tot * 100, 0)}%)")
        if v / tot > 0.06:
            ax.text(sx + v / 2, 0, f"{fmt_num(v / 1000)}k", ha="center", va="center", fontsize=8, color="#ffffff", fontweight="bold")
        sx += v
    ax.set_yticks([])
    ax.grid(axis="y", visible=False)
    ax.spines["left"].set_visible(False)
    _k_x(ax)
    ax.set_title("Composizione dell'imponibile", fontsize=10, loc="left")
    leg = ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=4)
    for txt in leg.get_texts():
        txt.set_color(t["fg"])
    return fig


def _k_x(ax):
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{fmt_num(v / 1000)}k"))
    ax.grid(axis="x", color="#cbd5e1", alpha=0.5, linewidth=0.6)


def fig_pv_categorie(categorie, tema="light"):
    """Costo e prezzo per categoria di lavorazione."""
    fig, (ax,) = _nuova(tema, w=7.6, h=3.2)
    t = _t(tema)
    cats = sorted(categorie, key=lambda c: c["Prezzo"])
    ys = range(len(cats))
    ax.barh([y + 0.2 for y in ys], [c["Costo"] for c in cats], height=0.38, color=SERIE[0], label="Costo diretto")
    ax.barh([y - 0.2 for y in ys], [c["Prezzo"] for c in cats], height=0.38, color=VERDE, label="Prezzo al cliente")
    ax.set_yticks(list(ys))
    ax.set_yticklabels([c["Categoria"] for c in cats], fontsize=8, color=t["fg"])
    ax.grid(axis="y", visible=False)
    _k_x(ax)
    ax.set_title("Costi e prezzi per categoria", fontsize=10, loc="left")
    _legenda(ax, tema, loc="lower right")
    return fig


def fig_pv_sensibilita(righe, tema="light"):
    """Margine al variare dei costi diretti, a prezzo invariato."""
    fig, (ax,) = _nuova(tema, w=7.6, h=3.0)
    t = _t(tema)
    xs = [(f"{r['Variazione costi %']:+.0f}%" if abs(r['Variazione costi %']) > 1e-9 else "0%") for r in righe]
    ys = [r["Margine %"] for r in righe]
    ax.bar(xs, ys, color=[VERDE if y >= 0 else ROSSO for y in ys], width=0.55)
    for x, y in zip(xs, ys):
        ax.text(x, y + (0.4 if y >= 0 else -0.4), f"{fmt_num(y, 1)}%", ha="center", va="bottom" if y >= 0 else "top", fontsize=8, color=t["fg"])
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    lo, hi = min(ys + [0]), max(ys + [0])
    ax.set_ylim(lo - (hi - lo) * 0.18 - 0.5, hi + (hi - lo) * 0.18 + 0.5)
    ax.set_xlabel("Variazione dei costi diretti rispetto al computo", fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}%"))
    ax.set_title("Margine se i costi aumentano (prezzo al cliente invariato)", fontsize=10, loc="left")
    return fig


# ----------------------------------------------------------------------------
# SCADENZARIO E CRUSCOTTO
# ----------------------------------------------------------------------------
def fig_sc_settimane(sett, fido=None, tema="light"):
    """Incassi e pagamenti previsti per settimana (barre) e cassa a fine settimana (linea)."""
    fig, (ax,) = _nuova(tema, w=7.6, h=4.0)
    t = _t(tema)
    xs = [r["Settimana"] for r in sett]
    ax.bar(xs, [r["Incassi"] for r in sett], color=VERDE, width=0.62, label="Incassi previsti")
    ax.bar(xs, [-r["Pagamenti"] for r in sett], color=ROSSO, width=0.62, alpha=0.85, label="Pagamenti previsti")
    ax.plot(xs, [r["Cassa finale"] for r in sett], color=SERIE[0], marker="o", markersize=3.5, linewidth=2, label="Cassa a fine settimana")
    if fido:
        ax.axhline(-fido, color=GIALLO, linestyle="--", linewidth=1.3, label=f"Limite del fido ({fmt_num(fido / 1000)}k)")
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set_xticks(xs)
    ax.set_xlabel("Settimana", fontsize=8)
    _k(ax)
    ax.set_title("Cassa settimana per settimana", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=4)
    return fig


def fig_sc_fasce(fasce, tema="light"):
    """Anzianita' dello scaduto: crediti (attive) e debiti (passive) per fascia di ritardo."""
    fig, (ax,) = _nuova(tema, w=7.2, h=3.2)
    xs = list(range(len(fasce)))
    ax.bar([x - 0.2 for x in xs], [f["Attive"] for f in fasce], width=0.4, color=SERIE[1], label="Da incassare")
    ax.bar([x + 0.2 for x in xs], [f["Passive"] for f in fasce], width=0.4, color=SERIE[3], label="Da pagare")
    ax.set_xticks(xs)
    ax.set_xticklabels([f["Fascia"] for f in fasce], fontsize=8, color=_t(tema)["fg"])
    _k(ax)
    ax.set_title("Anzianita' dei documenti aperti", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper right")
    return fig


# ----------------------------------------------------------------------------
# SAL E CONTABILITA' LAVORI
# ----------------------------------------------------------------------------
_STATO_COL = {"ok": VERDE, "warn": GIALLO, "bad": ROSSO}


def fig_sl_margini(commesse, tema="light"):
    """Margine preventivato (grigio) e margine finale previsto (colorato per stato) per ogni commessa."""
    n = max(1, len(commesse))
    fig, (ax,) = _nuova(tema, w=7.4, h=max(2.6, 0.62 * n + 1.4))
    t = _t(tema)
    ys = list(range(n))
    for i, d in enumerate(commesse):
        ax.barh(i + 0.2, d["Margine atteso %"], height=0.36, color="#94a3b8", label="Margine preventivato" if i == 0 else None)
        ax.barh(i - 0.2, d["Margine finale %"], height=0.36, color=_STATO_COL.get(d["Stato"], SERIE[0]), label="Margine finale previsto" if i == 0 else None)
    ax.set_yticks(ys)
    ax.set_yticklabels([d["Commessa"][:24] for d in commesse], fontsize=8, color=t["fg"])
    ax.invert_yaxis()
    ax.axvline(0, color=t["fg"], linewidth=0.9)
    ax.grid(axis="x", color=t["grid"], alpha=0.5, linewidth=0.6)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("% sul contratto", fontsize=8)
    ax.set_title("Margine: preventivato e previsto a fine lavori", fontsize=10, loc="left")
    _legenda(ax, tema, loc="lower right")
    return fig


def fig_sl_commessa(d, tema="light"):
    """Per una commessa: costi preventivati, valore maturato (EV), costi sostenuti e costi a finire attesi."""
    fig, (ax,) = _nuova(tema, w=6.6, h=3.0)
    voci = [("Costi\npreventivati", d["Costi preventivati"], "#94a3b8"), ("Valore\nmaturato (EV)", d["EV"], SERIE[0]),
            ("Costi\nsostenuti", d["Costi sostenuti"], SERIE[1]), ("Costi a finire\nattesi (EAC)", d["Costi a finire (EAC)"], _STATO_COL.get(d["Stato"], SERIE[2]))]
    ax.bar(range(len(voci)), [v[1] for v in voci], color=[v[2] for v in voci], width=0.55)
    for i, v in enumerate(voci):
        ax.text(i, v[1], fmt_num(v[1] / 1000) + "k", ha="center", va="bottom", fontsize=8, color=_t(tema)["fg"])
    ax.set_xticks(range(len(voci)))
    ax.set_xticklabels([v[0] for v in voci], fontsize=8, color=_t(tema)["fg"])
    _k(ax)
    ax.set_title(f"{d['Commessa']}: costi e valore maturato", fontsize=10, loc="left")
    return fig


# ----------------------------------------------------------------------------
# GRAFICI DEI MODULI OPERATIVI (gare, scadenze, mezzi, organico)
# ----------------------------------------------------------------------------
def fig_scadenze(conteggi, titolo="Stato delle scadenze", tema="light"):
    fig, (ax,) = _nuova(tema, w=6.4, h=2.4)
    t = _t(tema)
    voci = [("Scaduti", conteggi.get("bad", 0), ROSSO), ("In scadenza", conteggi.get("warn", 0), GIALLO), ("In regola", conteggi.get("ok", 0), VERDE)]
    ax.barh(range(3), [v[1] for v in voci], color=[v[2] for v in voci], height=0.55)
    for i, v in enumerate(voci):
        ax.text(v[1], i, f" {v[1]}", va="center", fontsize=9, color=t["fg"])
    ax.set_yticks(range(3))
    ax.set_yticklabels([v[0] for v in voci], fontsize=9, color=t["fg"])
    ax.invert_yaxis()
    ax.set_xlim(0, max(1, max(v[1] for v in voci)) * 1.18)
    ax.grid(axis="y", visible=False)
    ax.set_title(titolo, fontsize=10, loc="left")
    return fig


def fig_ga_gare(det, target, tema="light"):
    n = max(1, len(det))
    fig, (ax,) = _nuova(tema, w=7.2, h=max(2.4, 0.5 * n + 1.3))
    t = _t(tema)
    for i, d in enumerate(det):
        m = d["Margine %"]
        ax.barh(i, m, height=0.55, color=VERDE if m >= target else (GIALLO if m > 0 else ROSSO))
    ax.axvline(target, color=t["fg"], linewidth=1, linestyle="--")
    ax.axvline(0, color=t["fg"], linewidth=0.8)
    ax.set_yticks(range(n))
    ax.set_yticklabels([d["Gara"][:26] for d in det], fontsize=8, color=t["fg"])
    ax.invert_yaxis()
    ax.set_xlabel(f"Margine % sull'offerta (tratteggio = obiettivo {fmt_num(target, 0)}%)", fontsize=8)
    ax.grid(axis="y", visible=False)
    ax.set_title("Margine atteso con il ribasso scelto", fontsize=10, loc="left")
    return fig


def fig_og_carico(mesi, tema="light"):
    fig, (ax,) = _nuova(tema, w=7.2, h=3.0)
    t = _t(tema)
    x = list(range(len(mesi)))
    col = [ROSSO if m["Saturazione %"] > 100 else (GIALLO if m["Saturazione %"] < 60 else VERDE) for m in mesi]
    ax.bar(x, [m["Ore assegnate"] for m in mesi], color=col, width=0.6, label="Ore assegnate")
    ax.plot(x, [m["Capacità ore"] for m in mesi], color=t["fg"], marker="o", linewidth=1.4, label="Capacità")
    ax.set_xticks(x)
    ax.set_xticklabels([m["Mese"] for m in mesi], fontsize=8, color=t["fg"])
    ax.set_ylabel("ore", fontsize=8)
    ax.set_title("Carico di lavoro e capacità per mese", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper right")
    return fig


def fig_mz_costi(det, tema="light"):
    n = max(1, len(det))
    fig, (ax,) = _nuova(tema, w=7.2, h=max(2.4, 0.5 * n + 1.3))
    t = _t(tema)
    for i, d in enumerate(det):
        ax.barh(i, d["Costo imputato"], height=0.55, color=SERIE[0], label="Costo imputato alle commesse" if i == 0 else None)
        ax.barh(i, d["Fissi non assorbiti"], left=d["Costo imputato"], height=0.55, color=GIALLO, label="Costi fissi non assorbiti" if i == 0 else None)
    ax.set_yticks(range(n))
    ax.set_yticklabels([d["Mezzo"][:24] for d in det], fontsize=8, color=t["fg"])
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt_num(v / 1000) + "k"))
    ax.grid(axis="y", visible=False)
    ax.set_title("Costo dei mezzi: imputato e non assorbito (12 mesi)", fontsize=10, loc="left")
    _legenda(ax, tema, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2)
    return fig


def fig_rp_ore(cantieri, tema="light"):
    """Ore lavorate per cantiere nella finestra di osservazione (barre orizzontali, colore = rapportini regolari o in ritardo)."""
    cantieri = [c for c in cantieri if c["Ore"] > 0] or cantieri
    n = max(1, len(cantieri))
    fig, (ax,) = _nuova(tema, w=7.2, h=max(2.2, 0.5 * n + 1.2))
    t = _t(tema)
    col = {"ok": VERDE, "warn": GIALLO, "bad": ROSSO}
    for i, c in enumerate(cantieri):
        ax.barh(i, c["Ore"], height=0.55, color=col.get(c["Stato"], SERIE[0]))
    ax.set_yticks(range(n))
    ax.set_yticklabels([c["Cantiere"][:26] for c in cantieri], fontsize=8, color=t["fg"])
    ax.invert_yaxis()
    ax.set_xlabel("ore lavorate (colore: verde rapportini regolari, giallo/rosso in ritardo)", fontsize=8)
    ax.set_title("Ore lavorate per cantiere", fontsize=10, loc="left")
    return fig


GT_COL = {"ok": "#2563eb", "warn": "#f59e0b", "bad": "#ef4444", "done": "#22c55e", "wait": "#94a3b8"}


def fig_gt(out, tema="light", solo_commesse=False, commessa=None):
    """Diagramma di Gantt: barra chiara = durata prevista, barra piena = avanzamento reale, tratteggio rosso = ritardo stimato, linea = oggi."""
    import datetime as _dt

    import matplotlib.dates as mdates
    from matplotlib.patches import Patch
    righe = []
    for c in out["commesse"]:
        if commessa and c["Commessa"] != commessa:
            continue
        righe.append(("c", c["Commessa"], _dt.date.fromisoformat(c["Inizio"]), _dt.date.fromisoformat(c["Fine"]), c["Avanzamento"], c["Stato"], _dt.date.fromisoformat(c["Fine stimata"])))
        if not solo_commesse:
            for f in out["fasi"]:
                if f["Commessa"] == c["Commessa"]:
                    righe.append(("f", "   " + f["Fase"], f["d0"], f["d1"], f["Avanzamento"], f["Stato"], _dt.date.fromisoformat(f["Fine stimata"])))
    n = max(1, len(righe))
    fig, (ax,) = _nuova(tema, w=9.0, h=max(2.4, 0.34 * n + 1.3))
    t = _t(tema)
    oggi = out["params"]["oggi"]
    for i, (tipo, nome, d0, d1, av, st, fs) in enumerate(righe):
        h = 0.62 if tipo == "c" else 0.42
        x0, w = mdates.date2num(d0), max(1, (d1 - d0).days)
        ax.barh(i, w, left=x0, height=h, color=t["fg"] if tipo == "c" else GT_COL["wait"], alpha=0.16 if tipo == "c" else 0.35, zorder=2)
        ax.barh(i, w * av / 100.0, left=x0, height=h, color=GT_COL[st], zorder=3)
        if fs > d1 and st in ("ok", "warn", "bad"):
            ax.barh(i, (fs - d1).days, left=mdates.date2num(d1), height=h * 0.7, color=ROSSO, alpha=0.35, hatch="////", edgecolor=ROSSO, linewidth=0, zorder=2)
    ax.axvline(mdates.date2num(oggi), color=ROSSO, linestyle="--", linewidth=1.2, zorder=4)
    ax.text(mdates.date2num(oggi), -0.9, "oggi", color=ROSSO, fontsize=7, ha="center")
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[1][:30] for r in righe], fontsize=8, color=t["fg"])
    for lab, r in zip(ax.get_yticklabels(), righe):
        if r[0] == "c":
            lab.set_fontweight("bold")
    ax.invert_yaxis()
    ax.xaxis_date()
    span = (max(r[6] for r in righe) - min(r[2] for r in righe)).days if righe else 30
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=1 if span <= 240 else 2 if span <= 540 else 3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.tick_params(axis="x", labelsize=8)
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Cronoprogramma dei cantieri", fontsize=10, loc="left")
    ax.legend(handles=[Patch(color=GT_COL["ok"], label="Nei tempi"), Patch(color=GT_COL["warn"], label="In ritardo"), Patch(color=GT_COL["bad"], label="Critica"),
                       Patch(color=GT_COL["done"], label="Completata"), Patch(color=GT_COL["wait"], alpha=0.5, label="Da iniziare"),
                       Patch(facecolor=ROSSO, alpha=0.35, hatch="////", label="Ritardo stimato")], fontsize=7, ncol=6, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False)
    return fig
