import subprocess
import time
import requests
import json
import os
import xml.etree.ElementTree as ET
import spacy
from spellchecker import SpellChecker
from tqdm import tqdm
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
import nltk
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('omw-1.4')
stop_words = set(stopwords.words('english'))
lemmatizer = WordNetLemmatizer()
nlp = spacy.load("en_core_web_sm")
spell = SpellChecker()

# Konfiguration
RUN_FILE = 'baseline-title-abstract-query_expanded.run'
QRELS_FILE = "qrels-covid_d5_j0.5-5.txt"
TREC_EVAL_PATH = "/Users/alex/Solr-Abgabe/trec_eval/trec_eval"
TAG = 'solr-bm25'
TOPICFILE = 'topics-rnd5.xml'
OUTPUT_FILE = "trec_eval_expanded_results.txt"
FIELDS = "&fl=id,score,tag"
ROWS = "&rows=1000"
SOLR_DIR = "/Users/alex/solr-9.7.0"
SOLR_PORT = 8983
CORE_NAME = "expanded_core"
DATA = "/Users/alex/Solr-Abgabe/Endabgabe/processed_output_spacy_complete.csv"
BASE_URL = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select?q="
OPENAI_API_KEY = ""  
OPENAPI_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = ""  
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Solr-Management
def start_solr():
    subprocess.run([f"{SOLR_DIR}/bin/solr", "start", "-p", str(SOLR_PORT)], check=True)
    time.sleep(5)
    print("Solr gestartet")


def stop_solr():
    subprocess.run([f"{SOLR_DIR}/bin/solr", "stop", "-p", str(SOLR_PORT)])
    print("Solr beendet")


def delete_core():
    print("Löscht Core")
    subprocess.run([f"{SOLR_DIR}/bin/solr", "delete", "-c", CORE_NAME])


def create_core():
    print("Erstellt Core " + CORE_NAME)
    subprocess.run([f"{SOLR_DIR}/bin/solr", "create", "-c", CORE_NAME])


def import_data():
    print("Importiere Daten aus", DATA.split('/')[-1])
    subprocess.run([f"{SOLR_DIR}/bin/solr", "post", "-c", CORE_NAME, DATA])


def add_fields_to_solr(core_name, solr_port):
    fields = [
        {"name": "publish_time", "type": "string", "stored": True, "indexed": True},
        {"name": "arxiv_id", "type": "string", "stored": True, "indexed": True},
        {"name": "pubmed_id", "type": "string", "stored": True, "indexed": True},
        {"name": "all_text", "type": "text_general", "stored": False, "indexed": True},
        {"name": "title", "type": "text_general", "stored": True, "indexed": True},
        {"name": "authors", "type": "text_general", "stored": True, "indexed": True},
        {"name": "abstract", "type": "text_general", "stored": True, "indexed": True},
        {"name": "tag", "type": "text_general", "stored": True, "indexed": True}, 

    ]
    schema_url = f"http://localhost:{solr_port}/solr/{CORE_NAME}/schema"
    for field in fields:
        payload = {"add-field": field}
        response = requests.post(schema_url, json=payload, headers={"Content-type": "application/json"})
        if response.status_code == 200:
            print(f"Feld hinzugefügt: {field['name']}")
        else:
            print(f"Fehler beim Hinzufügen des Feldes {field['name']}: {response.text}")

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
    query_tag = ''.join(content.replace(',', '').split())
    return query_tag  # Gib das bereinigte Wort zurück

def lemquery(query):
    if not query:
        return ""
    words = query.split()
    corrected_words = []
    for w in words:
        best_guess = spell.correction(w)
        if best_guess is None:
            best_guess = w
        corrected_words.append(best_guess)

    corrected_query = " ".join(corrected_words)

    doc = nlp(corrected_query)
    lemmatized = [token.lemma_.lower() for token in doc if token.is_alpha]

    lemmatized_query = " ".join(lemmatized)

    return lemmatized_query
    
def preprocess_query(query):
    if not query:
        return ""
    words = query.split()
    processed = [lemmatizer.lemmatize(word) for word in words if word.lower() not in stop_words]
    lemmatized_query = " ".join(processed)
    return lemmatized_query

# Query und Run-File-Generierung
def generate_run_file_with_tags():
    print("Erstelle Run-File mit Tags für TREC Eval")
    if not os.path.isfile(TOPICFILE):
        topicsfile = requests.get('https://ir.nist.gov/covidSubmit/data/topics-rnd5.xml', allow_redirects=True)
        open(TOPICFILE, 'wb').write(topicsfile.content)
    with open(RUN_FILE, 'w') as f_out:
        root = ET.parse(TOPICFILE).getroot()
        for topic in root.findall('topic'):
            query = topic.find('query').text
            topic_id = topic.attrib['number']
            
            # Tags generieren
            with open('/Users/alex/Solr-Abgabe/Endabgabe/unique_tags.txt', 'r') as datei:
                tags = datei.readlines()  # Liste der Zeilen lesen
                tags = [zeile.strip() for zeile in tags]  # \n entfernen
            prompt = (
                f"This is your query: {query}. "
                f"Create a new one-word tag for this Query. Use only a tag from this list: {tags}"
                f"Don't respond with anything more than the tag. Don't use any formatting"
            )
            prompt2 = (
                f"This is your query: {query}. "
                f"Define me a time period which is relevant for this query. Use a format like YYYY-MM-DD TO YYYY-MM-DD "
                f"Don't respond with anything more then the time period"
            )
            query = preprocess_query(query)
            query_tag = call_gpt4(prompt)
            time_tag = call_gpt4(prompt2)
            prompt_timeboost = (
                f"This is your query: {query}. "
                f"You already defined this time period {time_tag}. Give a score between 0.0 to 1.0 on how relevant the time is for this query"
                f"Don't respond with anything more then the score an use this format X.X"
            )
            prompt_tagboost = (
                f"This is your tag: {query_tag}. "
                f"You have this query {query}. Give a score between 0.0 to 0.5 on how relevant the tag is for this query"
                f"Don't respond with anything more then the score an use this format X.XX"
            )
            # Finalisierte Query
            timetag_boost = call_gpt4(prompt_timeboost)
            querytag_boost = call_gpt4(prompt_tagboost)
            positionen = [10, 12]

            for pos in sorted(positionen, reverse=True):
                time_tag = time_tag[:pos] + " " + time_tag[pos:]
            
            full_query = f"title:({query})^0.5 abstract:({query})^1.5 tags:({query_tag})^{querytag_boost} publish_time:[{time_tag}]{timetag_boost} body_text:({query_tag})"
            print(full_query)
            url = f"{BASE_URL}{full_query}{FIELDS}{ROWS}"
            response = requests.get(url).json()
            rank = 1
            for doc in response.get('response', {}).get('docs', []):
                docid = doc.get("id")
                score = doc.get("score")
                docid = str(docid or "N/A").strip()
                score = str(score or 0).strip()

                out_str = f"{topic_id}\tQ0\t{docid}\t{rank}\t{score}\t{TAG}\t{query_tag}"
                f_out.write(out_str + '\n')
                rank += 1


# TREC_eval ausführen
def trec_eval():
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

    print("Ergebnisse:")
    with open(OUTPUT_FILE, "r") as output_file:
        print(output_file.read())


#Workflow
start_solr()
create_core()
add_fields_to_solr(CORE_NAME, SOLR_PORT)
import_data()
generate_run_file_with_tags()
trec_eval()
delete_core()
stop_solr()