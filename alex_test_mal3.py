import ollama
import xml.etree.ElementTree as ET
import os
import requests


# Load and parse the XML file
tree = ET.parse('topics-rnd5.xml')
root = tree.getroot()

# Extract queries
queries = [topic.find('query').text for topic in root.findall('topic')]

SOLR_DIR = "C:\\Users\\Patri\\Documents\\solr-8.11.4" 
SOLR_PORT = 8983
CORE_NAME = "testcore" 
METADATA_FILE = "C:\\Users\\Patri\\Downloads\\metadata.csv"
RUN_FILE = r'C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\baseline-title-abstract-query.run'
OUTPUT_FILE = "unique_tags.txt"
BASE_URL = f"http://localhost:{SOLR_PORT}/solr/{CORE_NAME}/select?q="
TAG = 'solr-bm25'
TOPICFILE = os.path.join("path", "to", "topics-rnd5.xml")
FIELDS = "&fl=id,score"
ROWS = "&rows=1000"

def read_tags_from_file(tags_file):
    """Reads tags and document IDs from the output file."""
    with open(tags_file, 'r') as file:
        tags_by_doc_id = [line.strip() for line in file]
    return tags_by_doc_id

def expand_query(queries, tags):
    prompt = f"""
    Expand each query {queries} by appending exactly one tag {tags} to it in the format: "query and tag".
    Only return the expanded queries.
    """
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": prompt}])
    return response['message']["content"]

def generate_run_file(new_queries):
    print("Erstelle Run-File für TREC Eval")
    if not os.path.isfile(TOPICFILE):
        topicsfile = requests.get('https://ir.nist.gov/covidSubmit/data/topics-rnd5.xml', allow_redirects=True)
        open(TOPICFILE, 'wb').write(topicsfile.content)

    with open(RUN_FILE, 'w') as f_out:
        root = ET.parse(TOPICFILE).getroot()
        topics = root.findall('topic')
        for i, topic in enumerate(topics):
            if i < len(new_queries):  # Check to prevent index out of range
                query = new_queries[i]
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

tags_by_doc_id = read_tags_from_file(OUTPUT_FILE) 
expanded = expand_query(queries, tags_by_doc_id)
generate_run_file(expanded)

