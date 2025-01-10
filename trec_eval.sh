#!/bin/bash

# Pfade zu den TREC_eval-Binaries und den Daten
TREC_EVAL_PATH="/Users/alex/Solr-Abgabe/trec_eval_win32/trec_eval.exe"  # Pfad zur ausführbaren TREC_eval-Datei
QRELS_FILE="/Users/alex/Solr-Abgabe/qrels-covid_d5_j0.5-5.txt"  # Pfad zur Qrels-Datei
RUN_FILE="/Users/alex/Solr-Abgabe/baseline-title-abstract-query.run"      # Pfad zur Run-Datei
OUTPUT_FILE="trec_eval_results.txt"  # Datei zur Speicherung der Ergebnisse

# Prüfen, ob die Dateien existieren
if [ ! -f "$TREC_EVAL_PATH" ]; then
    echo "Fehler: TREC_eval nicht gefunden unter $TREC_EVAL_PATH"
    exit 1
fi

if [ ! -f "$QRELS_FILE" ]; then
    echo "Fehler: Qrels-Datei nicht gefunden unter $QRELS_FILE"
    exit 1
fi

if [ ! -f "$RUN_FILE" ]; then
    echo "Fehler: Run-Datei nicht gefunden unter $RUN_FILE"
    exit 1
fi

# TREC_eval ausführen und Ergebnisse speichern
echo "Starte TREC_eval..."
$TREC_EVAL_PATH $QRELS_FILE $RUN_FILE > $OUTPUT_FILE

# Überprüfung des Exit-Status von TREC_eval
if [ $? -eq 0 ]; then
    echo "TREC_eval erfolgreich ausgeführt. Ergebnisse gespeichert in $OUTPUT_FILE"
else
    echo "Fehler beim Ausführen von TREC_eval."
    exit 1
fi

# Optional: Ergebnisse in der Konsole anzeigen
echo "Ergebnisse:"
cat $OUTPUT_FILE



#/Users/alex/Downloads/trec_eval-9.0.7 /Users/alex/Solr-Abgabe/qrels-covid_d5_j0.5-5.txt /Users/alex/Solr-Abgabe/baseline-title-abstract-query.run