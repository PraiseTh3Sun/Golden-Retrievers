import ollama
import csv
from collections import defaultdict
import xml.etree.ElementTree as ET

# Define file paths
METADATA_FILE = "/Users/alex/Solr-Abgabe/updated_metadata.csv"
RUN_FILE = r'/Users/alex/Solr-Abgabe/baseline-title-abstract-query.run'
OUTPUT_CSV = "/Users/alex/Solr-Abgabe/llm_metadata_cleaned.csv"
OUTPUT_TAGS_TXT = "/Users/alex/Solr-Abgabe/final/unique_tags.txt"

# Load document IDs from the RUN file
def load_document_ids(run_file):
    with open(run_file, 'r') as file:
        document_ids = [line[5:13].strip() for line in file]  # Reihenfolge bleibt erhalten
    document_ids = list(dict.fromkeys(document_ids))  # Entfernt Duplikate, Reihenfolge bleibt erhalten
    return document_ids

# Call LLM for tag generation
def llm(prompt):
    response = ollama.chat(
        model='llama3.2',
        messages=[
            {'role': 'user', 'content': prompt}
        ]
    )
    return response['message']['content']

# Tag documents with LLM and clean tags
def tag_documents(metadata_file, document_ids, output_csv, output_tags_txt, max_docs=1000):
    unique_tags = set()
    tagged_documents = []
    processed_count = 0  # Counter for processed documents

    # Erstelle ein Mapping von ID zu Reihenfolge
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

        for row in sorted_metadata:
            doc_id = row.get('id')
            abstract = row.get('abstract', '').strip()

            if processed_count >= max_docs:
                break

            # Generiere Tags mit LLM
            prompt = f"Create a one-word tag for this abstract. Don't respond with anything more than the tags. Don't use any formatting and use only the root word. Never use plural: {abstract}"
            try:
                tags = llm(prompt).replace('\n', '').strip()
                cleaned_tags = [tag.strip() for tag in tags.split(',') if tag.strip()]
                unique_tags.update(cleaned_tags)
                row['tags'] = ', '.join(cleaned_tags)
                tagged_documents.append({"id": doc_id, "tags": cleaned_tags})
                processed_count += 1
                print(f"Processed document {processed_count}: {doc_id}")
            except Exception as e:
                print(f"Error generating tags for document {doc_id}: {e}")
                row['tags'] = ''

            writer.writerow(row)

    # Schreibe einzigartige Tags in eine Textdatei
    with open(output_tags_txt, 'w', encoding='utf-8') as tag_file:
        for tag in sorted(unique_tags):
            tag_file.write(tag + '\n')

    return tagged_documents
# Read queries from the XML file
def extract_queries(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    return [topic.find('query').text.strip() for topic in root.findall('topic')]

# Main logic
def main():
    # Load relevant document IDs
    document_ids = load_document_ids(RUN_FILE)

    # Tag documents with a limit of 100
    tagged_documents = tag_documents(METADATA_FILE, document_ids, OUTPUT_CSV, OUTPUT_TAGS_TXT, max_docs=1000)

    # Build a dictionary of tags by document ID
    tags_by_doc_id = {doc['id']: doc['tags'] for doc in tagged_documents}



if __name__ == "__main__":
    main()
