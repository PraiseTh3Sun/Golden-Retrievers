import subprocess
import time
import requests
import json
import ollama

SOLR_DIR = "/Users/alex/solr-9.7.0"  # Pfad zu dem Solr-Verzeichnis
SOLR_PORT = 8983
CORE_NAME = "testcore"  # Name des verwendeten Cores
DATA = "/Users/alex/2020-07-16/metadata.csv"


def start_solr():
    subprocess.run(
        [f"{SOLR_DIR}/bin/solr", "start", "-p", str(SOLR_PORT)],
        check=True
    )
    time.sleep(5)  # Gibt Solr Zeit zum Starten
    print("Solr gestartet")


def stop_solr():
    subprocess.run(
        [f"{SOLR_DIR}/bin/solr", "stop", "-p", str(SOLR_PORT)],
    )
    print("Solr beendet")


def delete_core():
    print("Löscht Core")
    subprocess.run(
        [f"{SOLR_DIR}/bin/solr", "delete", "-c", CORE_NAME],
    )


def create_core():
    print("Erstellt Core " + CORE_NAME)
    subprocess.run(
        [f"{SOLR_DIR}/bin/solr", "create", "-c", CORE_NAME],
    )


def import_data():
    data_name = DATA.split('/')[-1]
    print("Importiere Daten aus " + data_name)
    subprocess.run(
        [f"{SOLR_DIR}/bin/solr", "post", "-c", CORE_NAME, DATA],
    )


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
        
        prompt = f"Create a one Word Tag for that abstract. Dont respond anything more then the tags. Create three of them: {abstract}"
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


start_solr()
create_core()
add_fields_to_schema()
add_fields_to_solr(CORE_NAME, SOLR_PORT)
import_data()
tag_documents_with_llm()  
query_solr(CORE_NAME, SOLR_PORT)
delete_core()
stop_solr()
