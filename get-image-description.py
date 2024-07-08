import argparse
import json
import os
from llmprocessor import LLMProcessor, FileCrawler

def get_image_metadata(folder_path, api_url, password="", recursive=False):
    llm_processor = LLMProcessor(api_url=api_url, password=password, chunk_size=1)
    file_crawler = FileCrawler()
    image_metadata_filename = get_output_filename(folder_path)
    previous_results = load_previous_results(image_metadata_filename)

    file_list = file_crawler.crawl(folder_path, recursive=recursive, categories=['image'])
    
    for category, files in file_list.items():
        for file_info in files:
            file_path = file_info['path']
            if file_path not in previous_results:
                caption = llm_processor.interrogate_image(file_path)
                if caption:
                    result = {
                        'caption': caption,
                        'metadata': file_info['file_metadata']
                    }
                    previous_results[file_path] = result
                    append_result(image_metadata_filename, {file_path: result})
                    print(f"Interrogated and appended: {file_path}")
                else:
                    print(f"Failed to interrogate: {file_path}")
            else:
                print(f"Skipped (already processed): {file_path}")

    print(f"All results saved to: {image_metadata_filename}")
    
def get_output_filename(directory):
    root_dir_name = os.path.basename(os.path.normpath(directory))
    return f"{root_dir_name}_results.json"
        
def load_previous_results(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading previous results: {e}")
    return {}

def append_result(filename, result):
    try:
        if os.path.exists(filename):
            with open(filename, 'r+', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    data = {}
                data.update(result)
                f.seek(0)
                json.dump(data, f, indent=2)
                f.truncate()
        else:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2)
    except IOError as e:
        print(f"Error appending result: {e}")

def main():
    parser = argparse.ArgumentParser(description='Describe images using multimodal LLM')
    parser.add_argument('--api-url', default='http://localhost:5001/api', help='the URL of the LLM API')
    parser.add_argument('--password', default='', help='server password')
    parser.add_argument("directory", help="Directory containing the images")
    parser.add_argument('--recursive', action='store_true', help='Crawl directory tree')
    
    args = parser.parse_args()

    get_image_metadata(args.directory, args.api_url, args.password, args.recursive)
    
if __name__ == "__main__":
    main()
