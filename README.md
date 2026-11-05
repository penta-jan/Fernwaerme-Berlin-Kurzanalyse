# Kurzanalyse: Fernwärme in der Berliner Wärmewende (Entwurf)

Verbindet offene Verbrauchsdaten des Energieatlas Berlin (Gas, Fernwärme je Block)
mit den Wärmeversorgungsgebieten des Berliner Wärmeplans 2026. Alle Zahlen im Text
werden beim Kompilieren aus den Ergebnisdateien berechnet (Pipeline: `zkopipeline.sty`).

```sh
python3 daten/abruf.py        # WFS-Daten laden (Geoportal Berlin, ca. 70 MB) -> daten/roh/
python3 daten/auswertung.py   # Verschneidung, Kennzahlen, Karte -> daten/ergebnis/, abb/
cd daten && python3 hiq.py && cd ..   # Fallstudie HIQ (Umriss: daten/hiq.geojson)
pdflatex kurzanalyse.tex && biber kurzanalyse && pdflatex kurzanalyse.tex && pdflatex kurzanalyse.tex
```

Voraussetzungen: Python 3 mit geopandas, matplotlib; TeX mit pgfplots, datatool, siunitx.
Daten: Geoportal Berlin, Datenlizenz Deutschland – Zero – 2.0.
