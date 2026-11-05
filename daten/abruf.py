#!/usr/bin/env python3
"""Lädt die offenen Geodaten (WFS, Geoportal Berlin) für die Kurzanalyse.

Quellen (Datenlizenz Deutschland – Zero – 2.0):
  ua_gas         Energieverbrauch Gas je Block / Bezirk (Energieatlas/Umweltatlas)
  ua_fernwaerme  Energieverbrauch Fernwärme je Block / Bezirk
  waermeplanung  Wärmeversorgungsgebiete des Berliner Wärmeplans 2026 (Teilblöcke)

Aufruf: python3 daten/abruf.py   (schreibt nach daten/roh/)
"""
import urllib.parse
import urllib.request
from pathlib import Path

BASIS = "https://gdi.berlin.de/services/wfs/"
ROH = Path(__file__).parent / "roh"

ABFRAGEN = {
    # Datei: (Dienst, Layer, Attribute oder None für alle)
    "gas_block.json": ("ua_gas", "a_sp08_10_3verbrauchgasblock",
                       "blknr,verbrauch_mwh,ausgeschlossen,verbrauch_mwh2022,ausgeschlossen2022,"
                       "verbrauch_mwh2021,ausgeschlossen2021,verbrauch_mwh2020,ausgeschlossen2020"),
    "fw_block.json": ("ua_fernwaerme", "a_verbrauchfwblock",
                      "blknr,verbrauch_mwh,verbrauch_mwh2022,verbrauch_mwh2021,verbrauch_mwh2020"),
    "gas_bez.json": ("ua_gas", "b_sp08_10_3verbrauchgasbez", None),
    "fw_bez.json": ("ua_fernwaerme", "b_verbrauchfwbez", None),
    "gas_geo.json": ("ua_gas", "a_sp08_10_3verbrauchgasblock",
                     "blknr,verbrauch_mwh,ausgeschlossen,geom"),
    "wvg_geo.json": ("waermeplanung", "aa_waermeversorgungsgeb_2045",
                     "wvg_2045,wvg_2045_diff,betr_wn_2045,schl5,geom"),
    "wvg_years.json": ("waermeplanung", "ae_waermeversorgungsgeb_2025",
                       "wvg_2025,betr_wn_2025,wvg_2030,wvg_2035,wvg_2040,wvg_2045,schl5"),
}


def main():
    ROH.mkdir(exist_ok=True)
    for datei, (dienst, layer, attribute) in ABFRAGEN.items():
        p = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
             "TYPENAMES": f"{dienst}:{layer}", "OUTPUTFORMAT": "application/json"}
        if attribute:
            p["PROPERTYNAME"] = attribute
        url = BASIS + dienst + "?" + urllib.parse.urlencode(p)
        print(f"lade {datei} ...", flush=True)
        with urllib.request.urlopen(url, timeout=900) as r:
            (ROH / datei).write_bytes(r.read())


if __name__ == "__main__":
    main()
