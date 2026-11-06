#!/usr/bin/env python3
"""Ordnet die Akteure im Health Innovation Quarter (HIQ) ihren statistischen Blöcken zu.

Quellen
- Akteure: Standortseite der Geschäftsstelle Zukunftsorte (zukunftsorte.berlin),
  ergänzt um Bundeseinrichtungen im Umriss.
- Adressen: WFS adressen_berlin (Geoportal Berlin); jede Adresse trägt die Blocknummer.
- Verbrauch: Umweltatlas Gas/Fernwärme je Block, Wärmeplan 2026 (siehe abruf.py).

Grenzen: Die Zuordnung erfolgt über die Hauptadresse. Ein Block kann mehrere Nutzer
enthalten, große Standorte erstrecken sich über mehrere Blöcke.

Ausgabe: daten/ergebnis/akteure_hiq.csv
"""
import csv
import json
import urllib.parse
import urllib.request
import warnings
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

warnings.filterwarnings("ignore")
HIER = Path(__file__).parent
ROH, ERG = HIER / "roh", HIER / "ergebnis"

# id, Name (für den Text), Straße, Hausnummer, Träger
AKTEURE = [
    ("virchow", "Charité Campus Virchow-Klinikum", "Augustenburger Platz", 1, "Land"),
    ("bnd", "Bundesnachrichtendienst", "Chausseestraße", 96, "Bund"),
    ("mitte", "Charité Campus Mitte, DRFZ", "Charitéplatz", 1, "Land"),
    ("mdc", "MDC-BIMSB, HU Campus Nord", "Hannoversche Straße", 28, "Bund/Land"),
    ("bwk", "Bundeswehrkrankenhaus", "Scharnhorststraße", 13, "Bund"),
    ("naturkunde", "Museum für Naturkunde, BMV, HU", "Invalidenstraße", 43, "Bund/Land"),
    ("bht", "Berliner Hochschule für Technik", "Luxemburger Straße", 10, "Land"),
    ("bmwe", "BMWE", "Scharnhorststraße", 34, "Bund"),
    ("futurium", "Futurium", "Alexanderufer", 2, "Bund"),
    ("bmftr", "BMFTR", "Kapelle-Ufer", 1, "Bund"),
    ("bayer", "Bayer (Hauptadresse)", "Müllerstraße", 178, "privat"),
]


KURZ = {
    "Wärmenetzgebiet - Bestand": "Bestand",
    "Wärmenetzgebiet - Erschließungsperspektive bis 2030": "bis 2030",
    "Wärmenetzgebiet - Erschließungsperspektive zwischen 2025 und 2030": "bis 2030",
    "Wärmenetzgebiet - Erschließungsperspektive zwischen 2030 und 2035": "2030--2035",
    "Wärmenetzgebiet - Erschließungsperspektive zwischen 2035 und 2040": "2035--2040",
    "Wärmenetzgebiet - Erschließungsperspektive zwischen 2040 und 2045": "2040--2045",
}


def adresse(strasse, hnr):
    f = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:And>'
         f'<fes:PropertyIsEqualTo><fes:ValueReference>str_name</fes:ValueReference>'
         f'<fes:Literal>{strasse}</fes:Literal></fes:PropertyIsEqualTo>'
         f'<fes:PropertyIsEqualTo><fes:ValueReference>hnr</fes:ValueReference>'
         f'<fes:Literal>{hnr}</fes:Literal></fes:PropertyIsEqualTo></fes:And></fes:Filter>')
    p = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
         "TYPENAMES": "adressen_berlin:adressen_berlin", "OUTPUTFORMAT": "application/json",
         "FILTER": f}
    url = "https://gdi.berlin.de/services/wfs/adressen_berlin?" + urllib.parse.urlencode(p)
    with urllib.request.urlopen(url, timeout=60) as r:
        treffer = json.load(r)["features"]
    ohne_zusatz = [t for t in treffer if not t["properties"].get("hnr_zusatz")]
    return (ohne_zusatz or treffer)[0]


def main():
    umriss = gpd.read_file(HIER / "hiq.geojson").to_crs(25833).union_all()
    g = gpd.read_file(ROH / "gas_geo.json").set_crs(25833, allow_override=True)
    fw = pd.DataFrame([f["properties"] for f in json.load(open(ROH / "fw_block.json"))["features"]])
    g = g.merge(fw[["blknr", "verbrauch_mwh"]], on="blknr", how="left",
                suffixes=("", "_fw")).set_index("blknr")
    w = gpd.read_file(ROH / "wvg_geo.json").set_crs(25833, allow_override=True)

    zeilen = []
    for aid, name, strasse, hnr, traeger in AKTEURE:
        a = adresse(strasse, hnr)
        blk = a["properties"]["blk"]
        pt = Point(a["geometry"]["coordinates"])
        b = g.loc[blk] if blk in g.index else None
        gas = "" if b is None or pd.isna(b.verbrauch_mwh) else round(b.verbrauch_mwh / 1e3, 3)
        fwv = "" if b is None or pd.isna(b.verbrauch_mwh_fw) else round(b.verbrauch_mwh_fw / 1e3, 3)
        status = "" if b is None or pd.isna(b.ausgeschlossen) else (
            "gesperrt" if "Datenschutz" in b.ausgeschlossen else "keine Angabe")
        wp = w[w.contains(pt)].wvg_2045.tolist()
        zeilen.append([aid, name, f"{strasse} {hnr}", traeger, blk,
                       "ja" if umriss.contains(pt) else "nein", gas, status, fwv,
                       wp[0] if wp else "", KURZ.get(wp[0], "") if wp else ""])
        print(f"{name:45s} {blk}  Gas {gas!s:>8}  {status:13s} FW {fwv!s:>7}  {wp[0] if wp else ''}")

    # Akteure im selben Block zu einer Zeile zusammenfassen (z. B. Futurium und BMFTR)
    zusammen = {}
    for z in zeilen:
        if z[4] in zusammen:
            alt = zusammen[z[4]]
            alt[1] += ", " + z[1]
            alt[2] += "; " + z[2]
            if z[3] not in alt[3].split("/"):
                alt[3] += "/" + z[3]
        else:
            zusammen[z[4]] = list(z)
    zeilen = list(zusammen.values())

    with open(ERG / "akteure_hiq.csv", "w", newline="") as f:
        cw = csv.writer(f, lineterminator="\n")
        cw.writerow(["id", "name", "adresse", "traeger", "block", "im-umriss",
                     "gas-gwh", "gas-status", "fw-gwh", "wvg-2045", "wvg-kurz"])
        cw.writerows(zeilen)


if __name__ == "__main__":
    main()
