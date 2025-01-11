import ollama 
import xml.etree.ElementTree as ET
import csv

# Load and parse the XML file
tree = ET.parse('topics-rnd5.xml')
root = tree.getroot()

# Extract queries
queries = [topic.find('query').text for topic in root.findall('topic')]

def expand_query(query):
    prompt = f"""
    Update these Queries: {query} and write them like this: #yourtext#. Use semantically similar or contextually relevant text to the original query. You are not allowed to write more than the query itself.
    """
    response = ollama.chat(model = "llama3.2", messages=[{"role": "user", "content": prompt}])
    return response['message']["content"]
# Expand the first query

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
    documents = "C:\\Users\\Patri\\Downloads\\metadata.csv"
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
        
tag_documents_with_llm()    
    # Aktualisierung in Solr

METADATA_FILE = "C:\\Users\\Patri\\Downloads\\metadata.csv"
RUN_FILE = r'C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\baseline-title-abstract-query.run'
OUTPUT_FILE = r'C:\Users\Patri\Downloads\unique_document_ids_cleaned.txt'

def read_metadata(file_path):
    documents = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            documents.append({
                "id": row.get("id"),
                "abstract": row.get("abstract", "")
            })
    return documents

def write_tags_to_output(output_file, unique_document_ids, tagged_documents):
    with open(output_file, 'w') as file:
        for doc_id in unique_document_ids:
            # Find matching document tags
            tags = next((doc['expanded_text'] for doc in tagged_documents if doc['id'] == doc_id), "No tags found")
            file.write(f"{doc_id}\t{tags}\n")

# Load metadata and generate tags
documents = read_metadata(METADATA_FILE)
tagged_documents = tag_documents_with_llm(documents)

# Process unique document IDs
with open(RUN_FILE, 'r') as file:
    document_ids = [line[5:13] for line in file]
    seen = set()
    unique_document_ids = []
    for doc_id in document_ids:
        if doc_id not in seen:
            unique_document_ids.append(doc_id)
            seen.add(doc_id)
    unique_document_ids = [doc_id.replace('\t', '') for doc_id in unique_document_ids]

# Write tags to output file
write_tags_to_output(OUTPUT_FILE, unique_document_ids, tagged_documents)