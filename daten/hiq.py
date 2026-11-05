#!/usr/bin/env python3
"""Fallstudie Health Innovation Quartier (HIQ), Zukunftsort Berlin.

Umriss: daten/hiq.geojson, zwei Teilflächen, nachgezeichnet nach dem
Wirtschaftsatlas Berlin (Business Location Center), November 2026.

Auswahlregel wie in der Pipeline: Hauptregel "innerhalb" (Block liegt ganz im
Umriss); zur Kontrolle "schneidet" und "mehr als 50 % der Blockfläche".
"""
import csv
import json
import warnings
from pathlib import Path

import geopandas as gpd
import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from auswertung import GRUPPEN, SPERRE, NETZ, FARBE, gruppe, legende_offiziell

warnings.filterwarnings("ignore")
HIER = Path(__file__).parent
ROH, ERG, ABB = HIER / "roh", HIER / "ergebnis", HIER.parent / "abb"


def main():
    hiq = gpd.read_file(HIER / "hiq.geojson").to_crs(25833)
    umriss = hiq.union_all()
    g = gpd.read_file(ROH / "gas_geo.json").set_crs(25833, allow_override=True)
    fw = pd.DataFrame([f["properties"] for f in json.load(open(ROH / "fw_block.json"))["features"]])
    g = g.merge(fw[["blknr", "verbrauch_mwh"]], on="blknr", how="left", suffixes=("", "_fw"))
    g["gesperrt"] = g["ausgeschlossen"].fillna("").str.contains(SPERRE)
    g["anteil"] = g.intersection(umriss).area / g.area

    kz = []

    def k(s, v, e, b):
        kz.append((s, round(float(v), 6), e, b))

    k("hiq-ha", hiq.area.sum() / 1e4, "ha", "Fläche des HIQ-Umrisses")
    regeln = {"innerhalb": g.within(umriss), "schneidet": g.intersects(umriss),
              "mehrheit": g["anteil"] > 0.5}
    for name, maske in regeln.items():
        s = g[maske]
        k(f"hiq-{name}-bloecke", len(s), "Blöcke", f"Blöcke ({name})")
        k(f"hiq-{name}-gas", s.verbrauch_mwh.sum() / 1e3, "GWh", f"Gas 2023 ({name})")
        k(f"hiq-{name}-fw", s.verbrauch_mwh_fw.sum() / 1e3, "GWh", f"Fernwärme 2023 ({name})")

    s = g[regeln["innerhalb"]]
    k("hiq-gas-mit-wert", s.verbrauch_mwh.notna().sum(), "Blöcke", "Gasblöcke mit Wert")
    k("hiq-gesperrt", s.gesperrt.sum(), "Blöcke", "Gasblöcke gesperrt")
    k("hiq-fw-mit-wert", s.verbrauch_mwh_fw.notna().sum(), "Blöcke", "Fernwärmeblöcke mit Wert")
    top2 = s.verbrauch_mwh.nlargest(2)
    k("hiq-gas-top2", top2.sum() / 1e3, "GWh", "Gas der zwei größten Blöcke")
    k("hiq-gas-top1", top2.iloc[0] / 1e3, "GWh", "Gas des größten Blocks")
    k("hiq-top1-ha", s.loc[top2.index[0]].geometry.area / 1e4, "ha", "Fläche des größten Blocks")
    k("hiq-top2-ha", s.loc[top2.index].geometry.area.sum() / 1e4, "ha", "Fläche der zwei größten Blöcke")
    k("hiq-gesperrt-ha", s[s.gesperrt].area.sum() / 1e4, "ha", "Fläche gesperrter Blöcke")
    # Vergleich mit Berlin: Dichte je Hektar Blockfläche, Sperrquote
    k("hiq-blockflaeche-ha", s.area.sum() / 1e4, "ha", "Blockfläche HIQ (innerhalb)")
    k("berlin-blockflaeche-ha", g.area.sum() / 1e4, "ha", "Blockfläche Berlin")
    k("berlin-gas-gwh", g.verbrauch_mwh.sum() / 1e3, "GWh", "Gas 2023 Berlin (sichtbar)")
    k("berlin-bloecke", len(g), "Blöcke", "Blöcke Berlin")
    k("berlin-gesperrt", g.gesperrt.sum(), "Blöcke", "Gasblöcke gesperrt Berlin")

    # Wärmeplan im Umriss: Gas flächenanteilig je Gebietstyp
    w = gpd.read_file(ROH / "wvg_geo.json").set_crs(25833, allow_override=True)
    w["gruppe"] = gruppe(w["wvg_2045"])
    s = s.copy()
    s["blockflaeche"] = s.area
    ov = gpd.overlay(s[["blknr", "verbrauch_mwh", "blockflaeche", "geometry"]],
                     w[["gruppe", "betr_wn_2045", "geometry"]], how="intersection",
                     keep_geom_type=True)
    ov["gas_gwh"] = ov.verbrauch_mwh.fillna(0) * ov.area / ov.blockflaeche / 1e3
    zeilen = [[gid, name, round(ov[ov.gruppe == gid].gas_gwh.sum(), 3), f"wp-{gid}"]
              for gid, name, _, _ in GRUPPEN if ov[ov.gruppe == gid].gas_gwh.sum() > 0.05]
    with open(ERG / "gebiete_hiq.csv", "w", newline="") as f:
        cw = csv.writer(f, lineterminator="\n")
        cw.writerow(["id", "name", "gas-gwh", "farbe"])
        cw.writerows(zeilen)
    k("hiq-gas-netz", ov[ov.gruppe.isin(NETZ)].gas_gwh.sum(), "GWh", "Gas in Wärmenetzgebieten 2045 (HIQ)")
    betr = ov[ov.gruppe.isin(NETZ)].betr_wn_2045.fillna("").unique()
    print("Betreiber im HIQ:", [b for b in betr if b])

    with open(ERG / "kennzahlen_hiq.csv", "w", newline="") as f:
        cw = csv.writer(f, lineterminator="\n")
        cw.writerow(["schluessel", "wert", "einheit", "beschreibung"])
        cw.writerows(kz)

    # Karte: Farben der offiziellen Wärmeplan-Legende; Umgebung aufgehellt,
    # Umriss schwarz mit weißem Saum, damit er auf allen Flächenfarben sichtbar ist
    import matplotlib.patheffects as pe
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    from shapely.geometry import box
    fig, ax = plt.subplots(figsize=(8.2, 5.0))
    xmin, ymin, xmax, ymax = hiq.total_bounds
    pad = 250
    rahmen = w.cx[xmin - pad:xmax + pad, ymin - pad:ymax + pad]
    rahmen.plot(ax=ax, color=rahmen["gruppe"].map(FARBE),
                linewidth=0.2, edgecolor="white")
    aussen = gpd.GeoSeries([box(xmin - pad, ymin - pad, xmax + pad, ymax + pad).difference(umriss)],
                           crs=hiq.crs)
    aussen.plot(ax=ax, color="white", alpha=0.55, linewidth=0)
    sg = g[regeln["innerhalb"] & g.gesperrt]
    sg.plot(ax=ax, facecolor="none", edgecolor="black", hatch="////", linewidth=0.6)
    hiq.boundary.plot(ax=ax, color="black", linewidth=2.2,
                      path_effects=[pe.Stroke(linewidth=5, foreground="white"), pe.Normal()])
    for _, r in g[regeln["innerhalb"]].nlargest(2, "verbrauch_mwh").iterrows():
        p = r.geometry.representative_point()
        ax.annotate(f"{r.verbrauch_mwh / 1e3:.0f} GWh Gas".replace(".", ","), (p.x, p.y),
                    fontsize=7, ha="center", bbox=dict(boxstyle="round", fc="white", lw=0.5))
    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_axis_off()
    legende_offiziell(ax, extra=[
        Patch(facecolor="none", edgecolor="black", hatch="////", label="Gasblock gesperrt (Datenschutz)"),
        Line2D([], [], color="black", linewidth=2.2,
               path_effects=[pe.Stroke(linewidth=5, foreground="white"), pe.Normal()],
               label="Health Innovation Quartier")],
        loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=7.5, frameon=False)
    fig.tight_layout()
    fig.savefig(ABB / "karte_hiq.pdf", dpi=250, bbox_inches="tight")
    for r in kz:
        print(r[0], r[1])


if __name__ == "__main__":
    main()
