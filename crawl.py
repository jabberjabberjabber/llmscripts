import os
import argparse
from collections import defaultdict
import json
from tika import parser
import ftfy
import re
from utils import APIHandler, NLPProcessor, FileHandler

def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    document_types = {
        '.txt': 'Text', '.pdf': 'PDF', '.doc': 'Word', '.docx': 'Word',
        '.xls': 'Excel', '.xlsx': 'Excel', '.ppt': 'PowerPoint', 
        '.pptx': 'PowerPoint', '.csv': 'CSV',
        '.xml': 'XML', '.html': 'HTML', '.htm': 'HTML'
    }
    if ext not in document_types:
        return None
    else:
        return document_types.get(ext)

def clean_text(text):
    if text is None:
        return ""
    text = ftfy.fix_text(text)
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def parse_document(file_path):
    parsed = parser.from_file(file_path)
    return parsed['content'], parsed['metadata']

def process_document(file_info, nlp_processor, tasks):
    content, tika_metadata = parse_document(os.path.join(file_info['location'], file_info['name']))
    cleaned_content = clean_text(content)
    result = {'file_info': file_info, 'tika_metadata': tika_metadata }
    if 'metadata' in tasks: result['llm_metadata'] = nlp_processor.process_text(cleaned_content, "metadata")
    if 'summarize' in tasks: result['summary'] = nlp_processor.process_text(cleaned_content, "summarize")
    if 'translate' in tasks: result['translate'] = nlp_processor.process_text(cleaned_content, "translate")
    if 'edit' in tasks: result['edit'] = nlp_processor.process_text(cleaned_content, "edit")
    return result

def find_and_process_files(directory, recursive=False, file_types=None, tasks=None, api_handler=None):
    file_list = defaultdict(list)
    nlp_processor = NLPProcessor(api_handler)
    file_handler = FileHandler()
    
    if recursive:
        walker = os.walk(directory)
    else:
        walker = [next(os.walk(directory))]
    for root, _, files in walker:
        for file in files:
            file_path = os.path.join(root, file)
            file_name, file_ext = os.path.splitext(file)
            file_type = get_file_type(file)
            if (file_types is None or file_type in file_types) and file_type is not None:
                file_info = {
                    'location': root,
                    'name': file,
                    'basename': file_name,
                    'ext': file_ext,
                    'type': file_type
                }
                if tasks is not None:
                    processed_info = process_document(file_info, nlp_processor, tasks)
                    is os.path
                    json_filename = f"{file_name}_info.json"
                    file_handler.write_file(os.path.join(root, json_filename), json.dumps(processed_info, indent=2))
                    file_info['info_file'] = json_filename
                file_list[file_type].append(file_info)
    return file_list
def main():
    parser = argparse.ArgumentParser(description='Find and process documents in filesystem')
    parser.add_argument('directory', help='Directory to search')
    parser.add_argument('-r', '--recursive', action='store_true', help='Search recursively')
    parser.add_argument('-t', '--types', nargs='+', help='File types to search for (e.g., PDF Word)')
    #parser.add_argument('--metadata', action='store_true', help='Generate metadata using LLM')
    #parser.add_argument('--summary', action='store_true', help='Generate summary using LLM')
    parser.add_argument('--api-url', default='http://172.16.0.219:5001/api', help='URL of the Kobold API')
    parser.add_argument('--password', default='', help='API password')
    parser.add_argument('--model', default='wizard', help='LLM model to use')
    parser.add_argument('--tasks', nargs='+',  default='info', help='Tasks: metadata, summarize, translate, edit, info')
    args = parser.parse_args()
    
    api_handler = APIHandler(args.api_url, args.password, args.model)
    file_list = find_and_process_files(args.directory, args.recursive, args.types, args.tasks, api_handler)

    for file_type, files in file_list.items():       
        print(f"\n{file_type} files:")
        for file in files:
            print(f"  {file['name']} - {file['location']}")
            if 'info_file' in file:
                print(f"    Info: {file['info_file']}")
    total_files = sum(len(files) for files in file_list.values())
    print(f"\nTotal files found: {total_files}")

if __name__ == "__main__":
    main()
