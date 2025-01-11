import ollama
import xml.etree.ElementTree as ET
import csv

# Load and parse the XML file
tree = ET.parse('topics-rnd5.xml')
root = tree.getroot()

# Extract queries
queries = [topic.find('query').text for topic in root.findall('topic')]

def read_tags_from_file(tags_file):
    """Reads tags and document IDs from the output file."""
    tags_by_doc_id = {}
    with open(tags_file, 'r') as file:
        for line in file:
            # Split by tab to extract document ID and tags
            parts = line.strip().split('\t')
            if len(parts) == 2:
                doc_id, tags = parts
                tags_by_doc_id[doc_id] = tags.split(',')  # Convert tags to a list
    return tags_by_doc_id

def expand_query(query, output_file):
    prompt = f"""
    Update these Queries: {query} and use the Outputfile {output_file} to expand the original Query. Use semantically similar or contextually relevant text to the original query. You are not allowed to write more than the query itself.
    """
    response = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": prompt}])
    return response['message']["content"]

def llm(prompt):
    response = ollama.chat(
        model='llama3.2',
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )
    print(response['message']['content'])
    return response['message']['content']

def tag_documents_with_llm(documents):
    updated_docs = []
    
    for doc in documents:
        doc_id = doc.get("id")  # Ensure doc is a dictionary
        abstract = doc.get("abstract", "")  
        
        if not abstract:
            print(f"Document {doc_id} has no 'abstract' field, skipping.")
            continue
        
        prompt = f"Create a one-word tag for this abstract. Don't respond with anything more than the tags. Create three of them: {abstract}"
        tags = llm(prompt)
        
        # Create updated document with tags
        updated_doc = {
            "id": doc_id,
            "expanded_text": tags
        }
        updated_docs.append(updated_doc)
    
    return updated_docs

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

# Define file paths
METADATA_FILE = "C:\\Users\\Patri\\Downloads\\metadata.csv"
RUN_FILE = r'C:\Users\Patri\Downloads\dis17-2024-main\dis17-2024-main\baseline-title-abstract-query.run'
OUTPUT_FILE = r'C:\Users\Patri\Downloads\unique_document_ids_cleaned.txt'

# Load metadata and generate tags
documents = read_metadata(METADATA_FILE)  # Parse the metadata file
tagged_documents = tag_documents_with_llm(documents)  # Generate tags

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
tags_by_doc_id = read_tags_from_file(OUTPUT_FILE) 
expand_query(queries, tags_by_doc_id)