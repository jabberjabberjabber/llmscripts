import os
import json
import argparse
from llmprocessor import LLMProcessor, TaskProcessor, FileUtils, FileCrawler

    
def extract_metadata(file_path, llm_processor, task_processor):
    content = FileUtils.read_file_content(file_path)
    tasks = ["metadata"]
    result = FileUtils.clean_json(json.dumps(task_processor.process_tasks(file_path, content=content, tasks=tasks)))

    llm_metadata = result.get('metadata', {})
    
    file_metadata = FileUtils.get_basic_metadata(file_path)
    combined_metadata = {
        "File": os.path.basename(file_path),
        "Title": llm_metadata.get("TITLE", "Unknown"),
        "Creator": "Unknown",
        "Author": llm_metadata.get("AUTHOR", "Not Specified"),
        "Subject": llm_metadata.get("SUBJECT", "Unknown"),
        "Topic": llm_metadata.get("TOPIC", "Unknown"),
        "Filetype": "",  # You might want to determine this dynamically
        "FullPath": file_path,
        "PreviousPath": "",
        "PreviousName": "",
        "Size (KB)": file_metadata['size'] // 1024,  # Convert bytes to KB
        "Created": file_metadata['created'],
        "Modified": file_metadata['modified'],
        "Category": "Document",  # You might want to determine this dynamically
        "Importance": 1  # You might want to calculate this somehow
    }
    
    return combined_metadata       
def process_documents(directory, api_url, api_password, task_config_path, output_path, prompt_config, model_name, recursive=False):
    file_crawler = FileCrawler()
    llm_processor = LLMProcessor(api_url=api_url, password=api_password, model=model_name, prompt_config=prompt_config)
    task_processor = TaskProcessor(llm_processor, task_config_path)

    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            central_metadata = json.load(f)
    else:
        central_metadata = {}

    file_list = file_crawler.crawl(directory, recursive, categories=["document"])
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
                    metadata = extract_metadata(file_path, llm_processor, task_processor)
                    central_metadata[file_name] = metadata  # Use filename as key

                    with open(output_path, 'w') as f:
                        json.dump(central_metadata, f, indent=2)
                except Exception as e:
                    print(f"\nError processing {file_path}: {str(e)}")
                    continue
    print(f"\nAll metadata saved to {output_path}")
    
def main():
    parser = argparse.ArgumentParser(description="Extract metadata from documents using LLM.")
    parser.add_argument("directory", help="Directory containing the documents")
    parser.add_argument("--api-url", required=True, default="http://localhost:5001/api", help="URL for the LLM API")
    parser.add_argument("--api-password", default="", help="Password for the LLM API")
    parser.add_argument("--task-config", default="query_metadata.json", help="Path to the task configuration file")
    parser.add_argument("--output", default="file_metadata.json", help="Output path for the central metadata JSON")
    parser.add_argument("--model-name", default="gemma2", help="completion, phi3, defaultJson, gemma2, llama3, llama3gap, llama3NoGap, llama3textStart, llama3SystemCompletion, llama3Completion, codestral, chatML, commandr, chatVicuna, samantha, alpaca, alpacaInstruct, llamav2, mistral, mixtral, wizard, wizardLM, vicuna, deepseek, deepseekCoder, deepseekv2")
    parser.add_argument("--prompt-config", default="prompt_config.json")
    parser.add_argument('--recursive', action='store_true', help='Crawl directory tree')
    
    args = parser.parse_args()
    
    process_documents(args.directory, api_url=args.api_url, api_password=args.api_password, task_config_path=args.task_config, output_path=args.output, prompt_config=args.prompt_config, model_name=args.model_name, recursive=args.recursive)

if __name__ == "__main__":
    main()
