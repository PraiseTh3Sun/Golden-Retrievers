import subprocess
import time
import requests
import json
import os
import xml.etree.ElementTree as ET
import ollama
import pandas as pd
from nltk.stem import PorterStemmer
from nltk.corpus import stopwords
import nltk
nltk.download('stopwords')
 
# Solr and file paths
SOLR_DIR = r"C:\Users\Patri\Downloads\solr-8.11.4\solr-8.11.4"
SOLR_PORT = 8983
CORE_NAME = "testcore"
DATA = r"C:\Users\Patri\Downloads\metadata.csv"
BASE_URL = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select?q="
RUN_FILE = 'baseline-title-abstract-query.run'
TAG = 'solr-bm25'
TOPICFILE = 'topics-rnd5.xml'
 
# Solr core fields
FIELDS = "&fl=cord_uid,score"
ROWS = "&rows=1000"
 
def remove_stopwords(text):
    """Remove stopwords from text."""
    stop_words = set(stopwords.words('english'))
    return ' '.join([word for word in text.lower().split() if word not in stop_words])
 
def stem_text(text):
    """Apply Porter stemming to text."""
    stemmer = PorterStemmer()
    return ' '.join([stemmer.stem(word) for word in text.lower().split()])
 
preprocessed_file = "preprocessed_metadata.csv"
if not os.path.isfile(preprocessed_file):
    def preprocess_csv(input_file, output_file):
        """Wendet Stopword-Entfernung und Stemming auf die relevanten Felder der CSV an."""
        df = pd.read_csv(input_file)
       
        # Gehe davon aus, dass die CSV eine Spalte 'abstract' enthält
        if 'abstract' in df.columns:
            df['abstract'] = df['abstract'].fillna('').apply(remove_stopwords).apply(stem_text)
       
        # Speichere die verarbeitete Datei
        df.to_csv(output_file, index=False)
        print(f"Datei wurde vorverarbeitet und in {output_file} gespeichert.")
 
    preprocess_csv(DATA, preprocessed_file)
 
DATA = preprocessed_file
 
 
# Solr Management Functions
def start_solr():
    subprocess.run([f"{SOLR_DIR}\\bin\\solr.cmd", "start", "-p", str(SOLR_PORT)], check=True)
    time.sleep(5)  # Wait for Solr to start
    print("Solr gestartet")
 
 
def stop_solr():
    subprocess.run([f"{SOLR_DIR}\\bin\\solr.cmd", "stop", "-p", str(SOLR_PORT)])
    print("Solr beendet")
 
 
def create_core():
    print("Erstellt Core " + CORE_NAME)
    subprocess.run([f"{SOLR_DIR}\\bin\\solr.cmd", "create", "-c", CORE_NAME])
 
 
def import_data():
    print("Importiere Daten")
    subprocess.run([f"{SOLR_DIR}\\bin\\solr.cmd", "post", "-c", CORE_NAME, DATA])
 
 
def add_fields_to_solr():
    fields = [
        {"name": "publish_time", "type": "string", "stored": True, "indexed": True},
        {"name": "arxiv_id", "type": "string", "stored": True, "indexed": True},
        {"name": "pubmed_id", "type": "string", "stored": True, "indexed": True},
        {"name": "all_text", "type": "text_general", "stored": False, "indexed": True},
        {"name": "title", "type": "text_general", "stored": True, "indexed": True},
        {"name": "authors", "type": "text_general", "stored": True, "indexed": True},
        {"name": "abstract", "type": "text_general", "stored": True, "indexed": True},
    ]
    schema_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/schema"
 
    for field in fields:
        payload = {"add-field": field}
        response = requests.post(schema_url, json=payload, headers={"Content-type": "application/json"})
        if response.status_code == 200:
            print(f"Feld '{field['name']}' erfolgreich hinzugefügt.")
        else:
            print(f"Fehler beim Hinzufügen des Feldes '{field['name']}':", response.text)
 
 
# LLM Integration
def llm(prompt):
    response = ollama.chat(
        model='llama3.2',
        messages=[{'role': 'user', 'content': prompt}]
    )
    return response['message']['content']
 
 
def tag_documents_with_llm():
    print("Tagging Dokumente mit dem LLM")
    query_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select"
    update_url = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/update?commit=true"
 
    response = requests.get(query_url, params={"q": "*:*", "rows": 100})
    documents = response.json().get("response", {}).get("docs", [])
    updated_docs = []
 
    for doc in documents:
        doc_id = doc.get("id")
        abstract = doc.get("abstract_txt", "")
 
        if not abstract:
            print(f"Dokument {doc_id} hat kein 'abstract_txt'-Feld, wird übersprungen.")
            continue
 
        prompt = f"Create three one-word tags for the following abstract: {abstract}"
        tags = llm(prompt)
 
        updated_doc = {"id": doc_id, "expanded_text": tags}
        updated_docs.append(updated_doc)
 
    if updated_docs:
        headers = {"Content-Type": "application/json"}
        update_response = requests.post(update_url, data=json.dumps(updated_docs), headers=headers)
        if update_response.status_code == 200:
            print("Dokumente erfolgreich aktualisiert.")
        else:
            print("Fehler beim Aktualisieren der Dokumente:", update_response.text)
 
 
# TREC Run File Generation
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
 
            q = f"title_txt:({query}) abstract_txt:({query})"
            url = f"{BASE_URL}{q}{FIELDS}{ROWS}"
            response = requests.get(url).json()
 
            rank = 1
            for doc in response.get('response', {}).get('docs', []):
                docid = doc.get("id")
                score = doc.get("score")
                out_str = f"{topic_id}\tQ0\t{docid}\t{rank}\t{score}\t{TAG}"
                f_out.write(out_str + '\n')
                rank += 1
 
 
# Main Execution Flow
#if __name__ == "__main__":
    #start_solr()
    #create_core()
    #add_fields_to_solr()
    #import_data()
    #tag_documents_with_llm()
    #generate_run_file()
    #stop_solr()
