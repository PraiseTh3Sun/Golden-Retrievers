import csv
import ollama

DATA = "/Users/alex/Solr-Abgabe/updated_metadata.csv"
OUTPUT_FILE = "/Users/alex/Solr-Abgabe/llm_metadata.csv"

RUN_FILE = r'/Users/alex/Solr-Abgabe/baseline-title-abstract-query.run'

# Dokument-IDs aus der RUN-Datei extrahieren
with open(RUN_FILE, 'r') as file:
    document_ids = [line[5:13] for line in file]

print(f"Gefilterte Dokument-IDs: {document_ids}")

def llm(prompt):
    response = ollama.chat(
        model='llama3.2', 
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )
    return response['message']['content']

def tag_documents_with_llm_from_csv():
    print("Tagging der Abstracts aus der CSV-Datei mit dem LLM.")
    
    # Einlesen der Original-CSV und Schreiben der neuen CSV
    with open(DATA, 'r', encoding='utf-8') as infile, open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['tags']  # Neue Spalte 'tags' hinzufügen
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        
        writer.writeheader()
        n = 0  # Zähler für die bearbeiteten Abstracts
        
        for row in reader:
            if row['id'] not in document_ids:
                writer.writerow(row)  # Dokument nicht in der Liste, unverändert schreiben
                continue
            
            if n >= 15:  # Stoppt nach 15 bearbeiteten Abstracts
                writer.writerow(row)  # Restliche Zeilen unverändert schreiben
                continue
            
            abstract = row.get('abstract', '')
            if not abstract.strip():
                print(f"Dokument {row['id']} hat kein gültiges 'abstract'. Übersprungen.")
                writer.writerow(row)  # Zeile ohne Änderungen schreiben
                continue
            
            # LLM-Aufruf, um Tags zu generieren
            prompt = f"Create a one-word tag for that abstract. Don't respond with anything other than the tags. Create three of them: {abstract}"
            try:
                tags = llm(prompt)
                row['tags'] = tags  # Tags in die neue Spalte schreiben
                n += 1
                print(f"Bearbeitetes Dokument {n}: {row['id']}")
            except Exception as e:
                print(f"Fehler beim Generieren der Tags für Dokument {row['id']}: {e}")
                row['tags'] = ''  # Leere Tags bei Fehler
            
            writer.writerow(row)  # Bearbeitete Zeile schreiben

    print(f"Tagging abgeschlossen. Aktualisierte Datei gespeichert unter: {OUTPUT_FILE}")

# Funktion aufrufen
tag_documents_with_llm_from_csv()
