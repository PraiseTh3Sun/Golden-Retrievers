import requests
import csv
import spacy
from spellchecker import SpellChecker

# Startet Spacy und SpellChecker
nlp = spacy.load("en_core_web_sm")
spell = SpellChecker()

# OpenAI API-Konfiguration
OPENAPI_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = ""  
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Pfade
METADATA_FILE = "/Users/alex/Solr-Abgabe/final/updated_metadata.csv"
RUN_FILE = r'/Users/alex/Solr-Abgabe/baseline-title-abstract-query.run'
OUTPUT_CSV = "/Users/alex/Solr-Abgabe/final/llm_metadata_cleaned.csv"
OUTPUT_TAGS_TXT = "/Users/alex/Solr-Abgabe/final/unique_tags.txt"
SKIPPED_DOCS_LOG = "/Users/alex/Solr-Abgabe/skipped_documents.log"

# Funktion zum Normalisieren von Tags mit Lemmatization und Spellchecking
def normalize_tags(tags):
    normalized = []
    for tag in tags:
        # Rechtschreibung wird korrigiert
        corrected_tag = spell.correction(tag)
        
        # Spacy macht Lemmatization
        doc = nlp(corrected_tag)
        lemmatized = [token.lemma_ for token in doc if token.is_alpha]
        
        # Wörter werden standardisiert
        lemmatized_cleaned = [word.lower() for word in lemmatized if word.is_alpha()]
        normalized.extend(lemmatized_cleaned)
    return normalized

# Dokument-IDs aus der Run-Datei laden
def load_document_ids(run_file):
    with open(run_file, 'r') as file:
        document_ids = [line.split()[2].strip() for line in file if len(line.split()) > 2]
    print(f"Es gibt {len(document_ids)} Dokumente vor der Duplikatentfernung")
    document_ids = list(dict.fromkeys(document_ids))
    print(f"Es gibt {len(document_ids)} Dokumente nach der Duplikatentfernung")
    return document_ids

maxdoc = len(load_document_ids(RUN_FILE))

def call_gpt4(prompt, model="gpt-4o-mini"):
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150,
        "temperature": 0.7
    }
    response = requests.post(OPENAPI_URL, headers=HEADERS, json=payload)
    response.raise_for_status()  # Fehler auslösen, falls der API-Aufruf fehlschlägt
    content = response.json()["choices"][0]["message"]["content"]
    # Entferne potenzielle Kommaseparierung einzelner Zeichen und kombiniere zu einem Wort
    content_cleaned = ''.join(content.replace(',', '').split())
    return content_cleaned  # Gib das bereinigte Wort zurück
    

# Fehlende IDs finden
def find_missing_ids(metadata_file, document_ids):
    with open(metadata_file, 'r', encoding='utf-8') as infile:
        reader = csv.DictReader(infile)
        metadata_ids = set(row['id'].strip() for row in reader)
    
    missing_ids = [doc_id for doc_id in document_ids if doc_id not in metadata_ids]
    print(f"Anzahl der fehlenden IDs: {len(missing_ids)}")
    if missing_ids:
        print("Fehlende IDs (erste 10):")
        for missing_id in missing_ids[:10]:
            print(missing_id)
    return missing_ids

# Dokumente taggen und Tags normalisieren
def tag_documents_with_existing_tags(metadata_file, document_ids, output_csv, output_tags_txt, max_docs=maxdoc):
    unique_tags = set()
    tagged_documents = []
    processed_count = 0  # Counter für verarbeitete Dokumente

    document_id_order = {doc_id: i for i, doc_id in enumerate(document_ids)}

    with open(metadata_file, 'r', encoding='utf-8') as infile, open(output_csv, 'w', encoding='utf-8', newline='') as outfile:
        reader = csv.DictReader(infile)
        fieldnames = reader.fieldnames + ['tags']
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        # Filtere und sortiere die Metadaten nach der Reihenfolge der IDs in der Runfile
        sorted_metadata = sorted(
            (row for row in reader if row['id'] in document_id_order),
            key=lambda row: document_id_order[row['id']]
        )
        print(f"Anzahl der sortierten Metadaten: {len(sorted_metadata)}")

        for row in sorted_metadata:
            doc_id = row.get('id')
            abstract = row.get('abstract', '')  # Standardwert: leerer String
            if not abstract:
                print(f"Skipping document {doc_id}: Abstract is missing or empty.")
                continue
            if processed_count >= max_docs:
                break

            # Generiere Tags mit GPT-4
            existing_tags = ', '.join(sorted(unique_tags))
            prompt = (
                f"Here is a list of existing tags: {existing_tags}. "
                f"Create a new one-word tag for this abstract. If there a tag, that is already fitting use it"
                f"Don't respond with anything more than the tag. Don't use any formatting: {abstract}"
            )
            try:
                tags = call_gpt4(prompt)
                cleaned_tags = [tags.strip()]  # Entfernt Leerzeichen und stellt sicher, dass es ein Wort ist
                
                # Normalisierung der Tags
                normalized_tags = normalize_tags(cleaned_tags)
                
                # Update der einzigartigen Tags
                unique_tags.update(normalized_tags)
                row['tags'] = ', '.join(normalized_tags)
                tagged_documents.append({"id": doc_id, "tags": normalized_tags})
                processed_count += 1
                print(f"Processed document {processed_count}: {doc_id} Tags: {cleaned_tags}")
            except Exception as e:
                row['tags'] = ', '.join(tags)
                processed_count += 1
                print(f"Processed document {processed_count}: {doc_id} Tags: {cleaned_tags}")
                unique_tags.update(tag.lower() for tag in cleaned_tags)

            row['tags'] = ', '.join(cleaned_tags)  # Die Tags werden hier in das CSV-Zeilen-Dictionary eingefügt
            writer.writerow(row)
    with open(output_tags_txt, 'w', encoding='utf-8') as tag_file:
        for tag in sorted(unique_tags):
            tag_file.write(tag + '\n')

    return tagged_documents

# Hauptprozess
document_ids = load_document_ids(RUN_FILE)

find_missing_ids(METADATA_FILE, document_ids)

tagged_documents = tag_documents_with_existing_tags(
    METADATA_FILE,
    document_ids,
    OUTPUT_CSV,
    OUTPUT_TAGS_TXT,
    max_docs=maxdoc
)

tags_by_doc_id = {doc['id']: doc['tags'] for doc in tagged_documents}