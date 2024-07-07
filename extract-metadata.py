import os
import json
import argparse
from llmprocessor import LLMProcessor, TaskProcessor, FileUtils, FileCrawler

    
def extract_metadata(file_path, llm_processor, task_processor):
    content = FileUtils.read_file_content(file_path)
    metadata_task = {
        "instruction": "Extract the title and author from this document. Return the result as JSON with 'title' and 'author' fields.",
        "num_chunks": 1,
        "parameters": {"temperature": 0.7, "min_p": 0.05, "top_p": 0.9}
    }
    result = task_processor.process_tasks(file_path, content=content, tasks=["metadata"])
    
    # Check if result is a dictionary
    if isinstance(result, dict):
        extracted_metadata = result.get("metadata", "{}")
    else:
        # If result is not a dictionary, treat it as a string
        extracted_metadata_str = FileUtils.clean_json(result) 
        extracted_metadata = extracted_metadata_str.get("metadata", "{}")
    if isinstance(extracted_metadata, str):
        try:
            extracted_metadata = FileUtils.json.loads(extracted_metadata)
        except json.JSONDecodeError:
            extracted_metadata = {}
    
    return {
        "title": extracted_metadata.get("title", "Unknown"),
        "author": extracted_metadata.get("author", "Unknown"),
        **FileUtils.get_basic_metadata(file_path)
    }
def process_documents(directory, api_url, api_password, task_config_path, output_path, prompt_config, model_name):
    file_crawler = FileCrawler()
    llm_processor = LLMProcessor(api_url=api_url, password=api_password, model=model_name, prompt_config=prompt_config)
    task_processor = TaskProcessor(llm_processor, task_config_path)
    

    if os.path.exists(output_path):
        with open(output_path, 'r') as f:
            central_metadata = json.load(f)
    else:
        central_metadata = {}


    file_list = file_crawler.crawl(directory, recursive=False, categories=["document"])
    total_files = sum(len(files) for files in file_list.values())
    processed_files = 0
    
    for category, files in file_list.items():
        for file_info in files:
            file_path = file_info['path']
            if file_path not in central_metadata:
                processed_files += 1
                #current_time = datetime.now().strftime("%H:%M:%S")
                #print(f"\rProcessing file {processed_files} of {total_files}: {file_path}", end="", flush=True)
                
                try:
                    metadata = extract_metadata(file_path, llm_processor, task_processor)
                    central_metadata[file_path] = metadata

                    with open(output_path, 'w') as f:
                        json.dump(central_metadata, f, indent=2)
                except Exception as e:
                    print(f"\nError processing {file_path}: {str(e)}")
                    continue
    print(f"\nAll metadata saved to {output_path}")
    
def main():
    parser = argparse.ArgumentParser(description="Extract metadata from documents using LLM.")
    parser.add_argument("directory", help="Directory containing the documents")
    parser.add_argument("--api-url", required=True, help="URL for the LLM API")
    parser.add_argument("--api-password", required=True, help="Password for the LLM API")
    parser.add_argument("--task-config", default="task_config.json", help="Path to the task configuration file")
    parser.add_argument("--output", default="central_metadata.json", help="Output path for the central metadata JSON")
    parser.add_argument("--model-name", default="gemma2")
    parser.add_argument("--prompt-config", default="prompt_config.json")
    
    args = parser.parse_args()
    
    process_documents(args.directory, api_url=args.api_url, api_password=args.api_password, task_config_path=args.task_config, output_path=args.output, prompt_config=args.prompt_config, model_name=args.model_name)

if __name__ == "__main__":
    main()
