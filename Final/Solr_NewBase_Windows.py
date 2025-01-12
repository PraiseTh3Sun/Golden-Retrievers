import subprocess
import time
import requests
import json
import ollama
import os
import xml.etree.ElementTree as ET


RUN_FILE = r'C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\baseline-title-abstract-query.run'
QRELS_FILE = r"C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\qrels-covid_d5_j0.5-5.txt"
TREC_EVAL_PATH = r"C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\trec_eval.exe"
TAG = 'solr-bm25'
TOPICFILE = r'C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\topics-rnd5.xml'
OUTPUT_FILE = r"C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\trec_eval_results.txt"
# Solr core fields
FIELDS = "&fl=id,score"
ROWS = "&rows=1000"
SOLR_DIR = r"C:\Users\Patri\Documents\solr-8.11.4"  # Pfad zu dem Solr-Verzeichnis
SOLR_PORT = 8983
CORE_NAME = "testcore"  # Name des verwendeten Cores
DATA = r"C:\Users\Patri\Downloads\metadata.csv"
BASE_URL = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select?q="


def start_solr():
    solr_script = os.path.join(SOLR_DIR, "bin", "solr.cmd")
    subprocess.run(
        [solr_script, "start", "-p", str(SOLR_PORT)],
        check=True,
        shell=True  # Erforderlich für Windows
    )
    time.sleep(5)  # Gibt Solr Zeit zum Starten
    print("Solr gestartet")


def stop_solr():
    solr_script = os.path.join(SOLR_DIR, "bin", "solr.cmd")
    subprocess.run(
        [solr_script, "stop", "-p", str(SOLR_PORT)],
        check=True,
        shell=True
    )
    print("Solr beendet")


def delete_core():
    print("Löscht Core")
    solr_script = os.path.join(SOLR_DIR, "bin", "solr.cmd")
    subprocess.run(
        [solr_script, "delete", "-c", CORE_NAME],
        check=True,
        shell=True
    )


def create_core():
    print("Erstellt Core " + CORE_NAME)
    solr_script = os.path.join(SOLR_DIR, "bin", "solr.cmd")
    subprocess.run(
        [solr_script, "create", "-c", CORE_NAME],
        check=True,
        shell=True
    )


def import_data():
    data_name = os.path.basename(DATA)
    print("Importiere Daten aus " + data_name)
    url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/update?commit=true"
    headers = {"Content-Type": "application/csv"}  # Adjust if JSON or XML
    
    # Read the CSV file and send it to Solr
    with open(DATA, 'rb') as file:
        response = requests.post(url, headers=headers, data=file)


def add_fields_to_schema():
    schema_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/schema"
    new_field = {
        "add-field": {
            "name": "expanded_text",
            "type": "text_general",
            "stored": True,
            "indexed": True
        }
    }
    response = requests.post(schema_url, json=new_field)
    if response.status_code == 200:
        print("Feld 'expanded_text' erfolgreich hinzugefügt.")
    else:
        print("Fehler beim Hinzufügen des Felds:", response.text)


def llm(prompt):
    response = ollama.chat(
        model='llama3.2', 
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )
    print(response['message']['content'])
    return response['message']['content']


def tag_documents_with_llm():
    print("Tagging der ersten 100 Dokumente mit dem LLM")
    query_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select"
    update_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/update?commit=true"
    
    # Abrufen der ersten 100 Dokumente
    response = requests.get(query_url, params={"q": "*:*", "rows": 100})
    documents = response.json().get("response", {}).get("docs", [])
    updated_docs = []
    
    for doc in documents:
        doc_id = doc.get("id")
        abstract = doc.get("abstract", "")  
        
        if not abstract:
            print(f"Dokument {doc_id} hat kein 'extract'-Feld, wird übersprungen.")
            continue
        
        prompt = f"Create one one-word tag for the following abstract: {abstract}"
        tags = llm(prompt)
        
        # Aktualisiertes Dokument erstellen
        updated_doc = {
            "id": doc_id,
            "expanded_text": tags 
        }
        updated_docs.append(updated_doc)
    
    # Aktualisierung in Solr
    if updated_docs:
        headers = {"Content-Type": "application/json"}
        update_response = requests.post(update_url, data=json.dumps(updated_docs), headers=headers)
        if update_response.status_code == 200:
            print("Dokumente erfolgreich aktualisiert.")
        else:
            print("Fehler beim Aktualisieren der Dokumente:", update_response.text)

def add_fields_to_solr(core_name, solr_port):
    fields = [
        {"name": "publish_time", "type": "string", "stored": True, "indexed": True},
        {"name": "arxiv_id", "type": "string", "stored": True, "indexed": True},
        {"name": "pubmed_id", "type": "string", "stored": True, "indexed": True},
        {"name": "all_text", "type": "text_general", "stored": False, "indexed": True},
        {"name": "title", "type": "text_general", "stored": True, "indexed": True},
        {"name": "authors", "type": "text_general", "stored": True, "indexed": True},
        {"name": "abstract", "type": "text_general", "stored": True, "indexed": True},
    ]
    schema_url = f"http://localhost:{solr_port}/solr/{CORE_NAME}/schema"
    
    for field in fields:
        payload = {"add-field": field}
        response = requests.post(schema_url, json=payload, headers={"Content-type": "application/json"})

def query_solr(core_name, solr_port):
    query_url = f"http://localhost:{solr_port}/solr/{core_name}/select"
    params = {
        "q": "expanded_text:*",
        "sort": "score desc",         
    }
    response = requests.get(query_url, params=params)
    results = response.json().get("response", {}).get("docs", [])
    print("Query-Ergebnisse:")
    for doc in results:
        print(doc)

def generate_run_file():
    print("Erstelle Run-File für TREC Eval")
    if not os.path.isfile(TOPICFILE):
        topicsfile = requests.get('https://ir.nist.gov/covidSubmit/data/topics-rnd5.xml', allow_redirects=True)
        open(TOPICFILE, 'wb').write(topicsfile.content)

    with open(RUN_FILE, 'w') as f_out:
        root = ET.parse(TOPICFILE).getroot()
        for topic in root.findall('topic'):
            query = topic.find('query').text
            topic_id = topic.attrib['number']

            q = f"title:({query}) abstract:({query})"
            url = f"{BASE_URL}{q}{FIELDS}{ROWS}"
            response = requests.get(url).json()
            rank = 1

            for doc in response.get('response', {}).get('docs', []):
                docid = doc.get("id")
                score = doc.get("score")

                # Sicherstellen, dass keine Listen oder Klammern in den Werten sind
                if isinstance(docid, list):
                    docid = docid[0]  # Ersten Wert der Liste nehmen
                if isinstance(score, list):
                    score = score[0]  # Ersten Wert der Liste nehmen

                # Fallback, falls Werte fehlen
                docid = str(docid or "N/A").strip()
                score = str(score or 0).strip()

                out_str = f"{topic_id}\tQ0\t{docid}\t{rank}\t{score}\t{TAG}"
                f_out.write(out_str + '\n')
                rank += 1

def check_file_exists(file_path):
    """Prüfen, ob eine Datei existiert."""
    if not os.path.isfile(file_path):
        print(f"Fehler: Datei nicht gefunden unter {file_path}")
        return False
    return True

def trec_eval():
    # Prüfen, ob die Dateien existieren
    if not check_file_exists(TREC_EVAL_PATH):
        return
    if not check_file_exists(QRELS_FILE):
        return
    if not check_file_exists(RUN_FILE):
        return

    print("Starte TREC_eval...")
    try:
        with open(OUTPUT_FILE, "w") as output_file:
            subprocess.run(
                [TREC_EVAL_PATH, QRELS_FILE, RUN_FILE],
                stdout=output_file,
                stderr=subprocess.PIPE,
                check=True
            )
        print(f"TREC_eval erfolgreich ausgeführt. Ergebnisse gespeichert in {OUTPUT_FILE}")
    except subprocess.CalledProcessError as e:
        print(f"Fehler beim Ausführen von TREC_eval: {e.stderr.decode().strip()}")
        return

    # Optional: Ergebnisse in der Konsole anzeigen
    print("Ergebnisse:")
    with open(OUTPUT_FILE, "r") as output_file:
        print(output_file.read())


start_solr()
create_core()
add_fields_to_schema()
add_fields_to_solr(CORE_NAME, SOLR_PORT)
import_data()
tag_documents_with_llm()  
query_solr(CORE_NAME, SOLR_PORT)
generate_run_file()
trec_eval()
delete_core()
stop_solr()

