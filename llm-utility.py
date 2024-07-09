import os
import json
import argparse
from llmprocessor import LLMProcessor, TaskProcessor, FileUtils, FileCrawler


def normalize_keys(input_dict):

    def normalize_key(key):
        if isinstance(key, str):
            return key.title()
        return key

    def process_value(value):
        if isinstance(value, dict):
            return normalize_keys(value)
        elif isinstance(value, list):
            return [process_value(item) for item in value]
        return value

    return {normalize_key(k): process_value(v) for k, v in input_dict.items()}

def extract_metadata(file_path, llm_processor, task_processor, category, caption=""):
    tasks = ["metadata"]
    
    if category == 'Document':
        content = FileUtils.read_file_content(file_path)
        init_result = FileUtils.clean_json(json.dumps(task_processor.process_tasks(file_path, content=content, tasks=tasks)))
        
    else:
        init_result = FileUtils.clean_json(json.dumps(task_processor.process_tasks(file_path, content=FileUtils.clean_content(caption), tasks=tasks)))
        

    result = normalize_keys(init_result)

        
    
    file_metadata = FileUtils.get_basic_metadata(file_path)
        
    llm_metadata = result.get('Metadata', {})
  

    combined_metadata = {
        "File": os.path.basename(file_path),
        "Title": llm_metadata.get("Title", "Unknown"),
        "Caption": caption,
        "Creator": llm_metadata.get("Creator", "Unknown"),
        "Author": llm_metadata.get("Author", "Not Specified"),
        "Subject": llm_metadata.get("Subject", "Unknown"),
        "Topic": llm_metadata.get("Topic", "Unknown"),
        "Filetype": "",
        "FullPath": os.path.abspath(file_path),
        "PreviousPath": "",
        "PreviousName": "",
        "Size (KB)": file_metadata['size'] // 1024,  # Convert bytes to KB
        "Created": file_metadata['created'],
        "Modified": file_metadata['modified'],
        "Category": category,  
        "ProposedFilename": llm_metadata.get("Filename", "unknown")  
    }
    
    return combined_metadata    


def process_files(directory, llm_processor, task_processor, output_path, categories):
    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            central_metadata = json.load(f)
    else:
        central_metadata = {}

    file_crawler = FileCrawler()
    file_list = file_crawler.crawl(directory, recursive=recursive, categories=categories)
    
    total_files = sum(len(files) for files in file_list.values())
    processed_files = 0

    for category, files in file_list.items():
        for file_info in files:
            file_path = file_info['path']
            file_name = os.path.basename(file_path)
            
            if file_name not in central_metadata:
                processed_files += 1
                print(f"\rProcessing file {processed_files} of {total_files}: {file_path}", end="", flush=True)
                
                try:
                    if category == 'image':
                        caption = llm_processor.interrogate_image(file_path)
                        if caption:
                            metadata = extract_metadata(file_path, llm_processor, task_processor, category="Image", caption=caption)

                        else:
                            print(f"\nFailed to interrogate: {file_path}")
                            continue
                    else:
                        metadata = extract_metadata(file_path, llm_processor, task_processor, category="Document", caption="")
                    
                    central_metadata[file_name] = metadata

                    with open(output_path, 'w') as f:
                        json.dump(central_metadata, f, indent=2)
                except Exception as e:
                    print(f"\nError processing {file_path}: {str(e)}")
                    continue
            else:
                print(f"\nSkipped (already processed): {file_path}")

    print(f"\nAll metadata saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Extract metadata from documents and images using LLM.")
    parser.add_argument("directory", help="Directory containing the files")
    parser.add_argument("--api-url", required=True, default="http://localhost:5001/api", help="URL for the LLM API")
    parser.add_argument("--api-password", default="", help="Password for the LLM API")
    parser.add_argument("--task-config", default="query_config.json", help="Path to the task configuration file")
    parser.add_argument("--output", default="file_metadata.json", help="Output path for the central metadata JSON")
    parser.add_argument("--model-name", default="phi3", help="LLM model name")
    parser.add_argument("--prompt-config", default="prompt_config.json")
    parser.add_argument('--recursive', action='store_true', help='Crawl directory tree')
    parser.add_argument('--categories', choices=['images', 'documents', 'all'], default='all', help='File categories to process')
    
    args = parser.parse_args()
    
    
    llm_processor = LLMProcessor(api_url=args.api_url, password=args.api_password, model=args.model_name, prompt_config=args.prompt_config)
    task_processor = TaskProcessor(llm_processor, args.task_config)
    global recursive
    if args.recursive:
        recursive = True
    else:
        recursive = False
        
    categories = []
    if args.categories == 'all':
        categories = ['document', 'image']
    elif args.categories == 'documents':
        categories = ['document']
    elif args.categories == 'images':
        categories = ['image']

    process_files(args.directory, llm_processor, task_processor, args.output, categories)

if __name__ == "__main__":
    main()
