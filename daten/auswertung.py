#!/usr/bin/env python3
"""Auswertung für die Kurzanalyse "Gas, Fernwärme und Transparenz in Berlin".

Eingang : daten/roh/*.json            (siehe abruf.py)
Ausgang : daten/ergebnis/*.csv        (von LaTeX gelesen)
          abb/karte.pdf               (Karte der Wärmeversorgungsgebiete)

Methode (Kurzfassung)
- Gasverbrauch je Block (Energieatlas, aktuellstes Jahr = 2023) wird flächen-
  anteilig auf die Teilblöcke des Wärmeplans 2026 verteilt (Verschneidung).
- Je Teilblock liegt das Wärmeversorgungsgebiet (2025 ... 2045) und der
  vorgesehene Netzbetreiber vor.
- Gesperrte Blöcke ("aus Datenschutzgründen nicht angezeigt") werden als
  Block-Äquivalente mitgezählt (Flächenanteil je Teilblock).
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

warnings.filterwarnings("ignore")
HIER = Path(__file__).parent
ROH, ERG = HIER / "roh", HIER / "ergebnis"
ABB = HIER.parent / "abb"
SPERRE = "Datenschutz"

# Gebietstypen des Wärmeplans (Feld wvg_2045) mit den Farben der offiziellen
# Legende (WMS waermeplanung, GetLegendGraphic, Layer aa_waermeversorgungsgeb_2045).
# Eine Tabelle für Karten, Balken und Kennzahlen, damit alles übereinstimmt.
# (id, Beschriftung, Werte im Feld wvg_2045, Farbe)
GRUPPEN = [
    ("bestand", "Wärmenetzgebiet – Bestand", ["Wärmenetzgebiet - Bestand"], "007256"),
    ("erw30", "Erschließung bis 2030",
     ["Wärmenetzgebiet - Erschließungsperspektive bis 2030",
      "Wärmenetzgebiet - Erschließungsperspektive zwischen 2025 und 2030"], "489A7D"),
    ("erw35", "Erschließung 2030–2035",
     ["Wärmenetzgebiet - Erschließungsperspektive zwischen 2030 und 2035"], "9BCFAF"),
    ("erw40", "Erschließung 2035–2040",
     ["Wärmenetzgebiet - Erschließungsperspektive zwischen 2035 und 2040"], "C6F2D7"),
    ("erw45", "Erschließung 2040–2045",
     ["Wärmenetzgebiet - Erschließungsperspektive zwischen 2040 und 2045"], "D5FEE5"),
    ("pruefhoch", "Prüfgebiet – hohe Wärmenetzeignung", ["Prüfgebiet - hohe Wärmenetzeignung"], "9185BE"),
    ("pruefgeg", "Prüfgebiet – Wärmenetzeignung gegeben", ["Prüfgebiet - Wärmenetzeignung gegeben"], "F5B4CB"),
    ("dezentral", "Dezentrale Versorgung", ["Gebiet der dezentralen Versorgung"], "F39300"),
    ("ohne", "Ohne relevanten Wärmebedarf", ["Gebiet ohne berechneten Wärmebedarf",
                                             "Gebiet ohne relevanten Wärmeverbrauch"], "E6E6E6"),
]
NETZ = {"bestand", "erw30", "erw35", "erw40", "erw45"}
PRUEF = {"pruefhoch", "pruefgeg"}
ZUORDNUNG = {wert: gid for gid, _, werte, _ in GRUPPEN for wert in werte}
FARBE = {gid: "#" + f for gid, _, _, f in GRUPPEN}
OHNE = FARBE["ohne"]


def gruppe(serie):
    """wvg_2045-Werte -> Gruppen-id (fehlende Werte: 'ohne')."""
    return serie.map(ZUORDNUNG).fillna("ohne")


def legende_offiziell(ax, extra=(), **kw):
    from matplotlib.patches import Patch
    h = [Patch(facecolor=FARBE[gid], edgecolor="#bbbbbb", linewidth=0.3, label=name)
         for gid, name, _, _ in GRUPPEN if gid != "ohne"]
    ax.legend(handles=h + list(extra), **kw)


def schreibe_farben():
    """LaTeX-Farbdefinitionen aus derselben Tabelle (für Balken und Diagramme)."""
    with open(ERG / "farben.tex", "w") as f:
        f.write("% erzeugt von daten/auswertung.py -- nicht von Hand ändern\n")
        for gid, name, _, hexwert in GRUPPEN:
            f.write(f"\\definecolor{{wp-{gid}}}{{HTML}}{{{hexwert}}}% {name}\n")


def props(datei):
    return pd.DataFrame([f["properties"] for f in json.load(open(ROH / datei))["features"]])


def schreibe(datei, kopf, zeilen):
    with open(ERG / datei, "w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(kopf)
        w.writerows(zeilen)


def main():
    ERG.mkdir(exist_ok=True)
    ABB.mkdir(exist_ok=True)
    kz = []  # Kennzahlen: schluessel, wert, einheit, beschreibung

    def k(schluessel, wert, einheit, beschreibung):
        kz.append((schluessel, round(float(wert), 6), einheit, beschreibung))

    # ---------------------------------------------------------- Bezirkssummen
    gb, fb = props("gas_bez.json"), props("fw_bez.json")
    jahre = range(2013, 2024)
    schreibe("zeitreihe.csv", ["jahr", "gas-twh", "fw-twh"],
             [[j, round(gb[f"j{j}g"].sum() / 1000, 4), round(fb[f"j{j}g"].sum() / 1000, 4)]
              for j in jahre])
    for j in (2021, 2023):
        k(f"gas-bez-{j}", gb[f"j{j}g"].sum() / 1000, "TWh", f"Gasverbrauch Berlin {j} (Bezirkssumme)")
        k(f"fw-bez-{j}", fb[f"j{j}g"].sum() / 1000, "TWh", f"Fernwärmeverbrauch Berlin {j} (Bezirkssumme)")

    # ---------------------------------------------------------- Blockdaten
    g, w = props("gas_block.json"), props("fw_block.json")
    k("bloecke", len(g), "", "Statistische Blöcke in Berlin")
    for suffix, jahr in (("", 2023), ("2022", 2022), ("2021", 2021), ("2020", 2020)):
        aus = g["ausgeschlossen" + suffix].fillna("")
        k(f"gas-gesperrt-{jahr}", aus.str.contains(SPERRE).sum(), "Blöcke",
          f"Gasblöcke gesperrt (Datenschutz) {jahr}")
    k("gas-gemeldet", g["verbrauch_mwh"].notna().sum(), "Blöcke", "Gasblöcke mit Wert 2023")
    k("gas-keine-angabe", g["ausgeschlossen"].fillna("").str.contains("Keine Angabe").sum(),
      "Blöcke", "Gasblöcke ohne Angabe 2023")
    k("gas-block-2023", g["verbrauch_mwh"].sum() / 1e6, "TWh", "Summe sichtbarer Gas-Blockwerte 2023")
    k("fw-block-2023", w["verbrauch_mwh"].sum() / 1e6, "TWh", "Summe sichtbarer Fernwärme-Blockwerte 2023")
    k("fw-mit-wert", w["verbrauch_mwh"].notna().sum(), "Blöcke", "Fernwärmeblöcke mit Wert 2023")
    both = pd.merge(g, w, on="blknr", suffixes=("_g", "_w"))
    k("gas-und-fw", (both.verbrauch_mwh_g.notna() & both.verbrauch_mwh_w.notna()).sum(),
      "Blöcke", "Blöcke mit Gas- und Fernwärmewert")

    # ---------------------------------------------------------- Verschneidung
    geo_g = gpd.read_file(ROH / "gas_geo.json").set_crs(25833, allow_override=True)
    geo_w = gpd.read_file(ROH / "wvg_geo.json").set_crs(25833, allow_override=True)
    geo_w = geo_w.merge(props("wvg_years.json"), on="schl5", how="left", suffixes=("", "_j"))
    geo_g["blockflaeche"] = geo_g.area
    ov = gpd.overlay(geo_g[["blknr", "verbrauch_mwh", "ausgeschlossen", "blockflaeche", "geometry"]],
                     geo_w, how="intersection", keep_geom_type=True)
    anteil = ov.area / ov["blockflaeche"]
    ov["gas_twh"] = ov["verbrauch_mwh"].fillna(0) * anteil / 1e6
    ov["gesperrt"] = ov["ausgeschlossen"].fillna("").str.contains(SPERRE) * anteil
    ov["gruppe"] = gruppe(ov["wvg_2045"])
    geo_w["gruppe"] = gruppe(geo_w["wvg_2045"])
    schreibe_farben()

    zeilen = []
    for gid, name, _, _ in GRUPPEN:
        t = ov[ov.gruppe == gid]
        zeilen.append([gid, name, round(t.gas_twh.sum(), 4), round(t.gesperrt.sum(), 1), f"wp-{gid}"])
        k(f"gas-{gid}", t.gas_twh.sum(), "TWh", f"Gas 2023 in: {name}")
    schreibe("gebiete.csv", ["id", "name", "gas-twh", "gesperrt", "farbe"], zeilen)
    k("gas-pruef", ov[ov.gruppe.isin(PRUEF)].gas_twh.sum(), "TWh", "Gas 2023 in Prüfgebieten (beide Typen)")

    netz = ov[ov.gruppe.isin(NETZ)]
    k("gas-netz-2045", netz.gas_twh.sum(), "TWh", "Gas 2023 in Wärmenetzgebieten 2045")
    k("gesperrt-netz", netz.gesperrt.sum(), "Block-Äq.", "Gesperrte Gasblöcke in Wärmenetzgebieten 2045")
    k("gesperrt-bestand", ov[ov.gruppe == "bestand"].gesperrt.sum(), "Block-Äq.",
      "Gesperrte Gasblöcke in Fernwärme-Bestandsgebieten")
    k("gas-sichtbar-ov", ov.gas_twh.sum(), "TWh", "Gas in der Verschneidung (Kontrolle)")

    # Stützjahre: kumuliert Gas in Wärmenetzgebieten, gestapelt nach Gebietstyp
    # (Bestand + Erschließungsstufen, die bis zum jeweiligen Stützjahr erreicht sind)
    stufen = [("bestand", 2025), ("erw30", 2030), ("erw35", 2035), ("erw40", 2040), ("erw45", 2045)]
    summe = {gid: ov[ov.gruppe == gid].gas_twh.sum() for gid, _ in stufen}
    schreibe("stuetzjahre.csv", ["jahr"] + [gid for gid, _ in stufen] + ["gas-twh"],
             [[j] + [round(summe[gid], 4) if bis <= j else 0 for gid, bis in stufen]
              + [round(sum(summe[gid] for gid, bis in stufen if bis <= j), 4)]
              for j in (2025, 2030, 2035, 2040, 2045)])

    # Betreiber
    b = netz["betr_wn_2045"].fillna("")
    grp = b.map(lambda s: "BEW allein" if s == "BEW Berliner Energie und Wärme GmbH"
                else ("BEW mit weiteren" if "BEW" in s else ("andere Betreiber" if s else "ohne Angabe")))
    t = netz.groupby(grp).gas_twh.sum().sort_values(ascending=False)
    # Betreiber haben keine Entsprechung in der Karte: neutrales Grau
    schreibe("betreiber.csv", ["id", "name", "gas-twh", "farbe"],
             [[i, n, round(v, 4), "black!40"] for i, (n, v) in enumerate(t.items(), 1)])
    k("gas-bew-allein", t.get("BEW allein", 0), "TWh", "Gas 2023 in Netzgebieten mit BEW als einzigem Betreiber")
    k("gas-bew-alle", t.get("BEW allein", 0) + t.get("BEW mit weiteren", 0), "TWh",
      "Gas 2023 in Netzgebieten mit BEW-Beteiligung")

    schreibe("kennzahlen.csv", ["schluessel", "wert", "einheit", "beschreibung"], kz)

    # ---------------------------------------------------------- Karte
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    farbe = geo_w["gruppe"].map(FARBE)
    geo_w.plot(ax=ax, color=farbe, linewidth=0, rasterized=True)
    gesperrt = geo_g[geo_g["ausgeschlossen"].fillna("").str.contains(SPERRE)]
    gesperrt.representative_point().plot(ax=ax, color="black", markersize=0.6, rasterized=True)
    ax.set_axis_off()
    from matplotlib.lines import Line2D
    legende_offiziell(ax, extra=[Line2D([], [], marker="o", color="black", linestyle="",
                                        markersize=2, label="Gasblock gesperrt (Datenschutz)")],
                      loc="lower left", fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(ABB / "karte.pdf", dpi=250)
    print("fertig:", ", ".join(p.name for p in ERG.iterdir()))


if __name__ == "__main__":
    main()
