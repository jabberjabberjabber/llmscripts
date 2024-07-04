import json
import os
import re
from llmer import LLMProcessor
import argparse
from collections import defaultdict, namedtuple
from tika import parser
from json_repair import repair_json
from natsort import os_sorted
from datetime import datetime


# -----------------------------
# Start of written by claud 3.5
# -----------------------------

# This was added so that the file order would be the same as
# Windows explorer
Node = namedtuple('Node', 'path isdir')

def scan_directory(path):
    """
    Scan a directory and return sorted Node objects using natsort.os_sorted().
    """
    try:
        with os.scandir(path) as it:
            # Create a list of Node objects for each entry in the directory
            entries = [Node(e.path, e.is_dir(follow_symlinks=False)) for e in it]
            
            # Use natsort.os_sorted() to sort the entries
            # This will sort in the same order as the operating system's file browser
            sorted_entries = os_sorted(entries, key=lambda x: x.path)
            
        return sorted_entries
    except OSError:
        # Return an empty list if there's an error (e.g., permission denied)
        return []

# ----------------------------
# end of written by claude 3.5
# ----------------------------

def get_basic_metadata(file_path):    
        created = os.path.getctime(file_path)
        modified = os.path.getmtime(file_path)
        return{
            'size': os.path.getsize(file_path),
            'created': datetime.fromtimestamp(created).isoformat(),
            'modified': datetime.fromtimestamp(modified).isoformat()
        }
    
def clean_json(data):
    '''
    llms can output json but some of them like to add commentary or 
    code blocks before the json, and sometimes they screw it up
    slightly. Also, sometimes json comes in a string instead
    of an object and when we dump it we get a lot of crap
    this removes line breaks and smart quotes, looks for 
    code blocks, and removes them.
    '''
    
    if data is None:
        return ""
    
    data = re.sub(r'\n', ' ', data)
    data = re.sub(r'["""]', '"', data)
        
    pattern = r'```json\s*(.*?)\s*```'
    match = re.search(pattern, data, re.DOTALL)
    
    if match:
        json_str = match.group(1).strip()
    else:
        json_str = re.search(r'\{.*\}', data, re.DOTALL)
        if json_str:
            json_str = json_str.group(0)
        else:
            return data 
    
    # Remove trailing comma if present
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    #using loads again undoes a lot of stupid crap
    return json.loads(repair_json(json_str))
    
def read_file_content(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except UnicodeDecodeError:
        return parse_with_tika(file_path)

def parse_with_tika(file_path):
    parsed = parser.from_file(file_path)
    return parsed.get('content', '')

def write_to_json(file_path, data):
    json_path = f"{file_path}_info.json"
    if os.path.exists(json_path):
        '''with open(json_path, 'r+') as file:
            existing_data = file.read()
            if existing_data == json_data:
                return
            json_data += "\n" + existing_data
            file.seek(0)
            file.write(json_data)
    '''
        print(f"File already exists: {json_path}")
        
    with open(json_path, 'w', encoding='utf-8') as file:
    
        json.dump(data, file, indent=2, ensure_ascii=False)
    print(f"Result written to: {json_path}")
    
def read_from_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            opened = file.read()
            return json.loads(opened)
            
    except:
        print(f"JSON error: {file_path}")
        return
        
class FileCrawler:
    def __init__(self):

        self.file_categories = {
            "document": ["txt", "pdf", "doc", "docx", "md", "rtf"],
            "spreadsheet": ["xls", "xlsx", "csv", "ods"],
            "presentation": ["ppt", "pptx", "odp"],
            "image": ["jpg", "jpeg", "png", "gif", "bmp", "tiff"],
            "audio": ["mp3", "wav", "ogg", "flac"],
            "video": ["mp4", "avi", "mov", "wmv", "flv", "mkv"],
            "web": ["html", "htm", "xml", "css", "js"],
            "code": ["py", "java", "cpp", "c", "js", "php", "rb"],
            "archive": ["zip", "rar", "7z", "tar", "gz"]
        }


# ------------------------------
# start of written by claude 3.5
# ------------------------------
    
    def crawl(self, directory, recursive=False, categories=None):
        file_list = defaultdict(list)
        walker = os.walk(directory) if recursive else [next(os.walk(directory))]

        for root, _, files in walker:
            sorted_files = os_sorted(files)
            for file in sorted_files:
                file_path = os.path.join(root, file)
                file_extension = os.path.splitext(file)[1].lower().lstrip('.')

                if self.should_include_file(file_extension, categories):
                    file_info = self.get_file_info(file_path, file_extension)
                    category = self.get_file_category(file_extension)
                    file_list[category].append(file_info)
        
        return file_list
            



    def should_include_file(self, file_extension, categories):
        if 'all' in categories:
            return True
        for category in categories:
            if category in self.file_categories:
                if file_extension in self.file_categories[category]:
                    return True
            elif file_extension == category:  # Direct extension match
                return True
        return False

    def get_file_category(self, file_extension):
        for category, extensions in self.file_categories.items():
            if file_extension in extensions:
                return category
        return "other"

    def get_file_info(self, file_path, file_extension):
        return {
            'path': file_path,
            'directory': os.path.dirname(file_path),
            'name': os.path.basename(file_path),
            'extension': file_extension,
            'category': self.get_file_category(file_extension),
            'metadata': get_basic_metadata(file_path)
        }


# ----------------------------
# end of written by claude 3.5
# ----------------------------

class TaskProcessor:
    '''
    there is a task_config.json dictionary file that 
    will have the instructions and promp parameters. this 
    gets loaded and the task is then exectuted accordingly
    '''
    
    def __init__(self, llm_processor, all_tasks_config):
        self.llm_processor = llm_processor
        self.all_tasks_config = read_from_json(all_tasks_config)
    
    
    def process_files(self, file_list, tasks=[]):
        results = {}
        for category, files in file_list.items():
            for file_info in files:
                file_path = file_info['path']
                content = read_file_content(file_path)
                result = self.process_tasks(file_info, content, tasks)
                if result:
                    results[file_path] = result
        return results

    def process_tasks(self, file_info, content, tasks):
        result = {'file_info': file_info}
        for task in tasks:
            try:
                if task not in self.all_tasks_config:
                    print(f"Invalid task: {task}")
                    result[task] = "Invalid task"
                    continue
                
                #load the config for the specific task and call the
                #llm to execute it
                task_config = self.all_tasks_config.get(task)
                
                #if we are summarizing something we don't necessarily
                #need to read the whole document, but if we are
                #translating it we do, so if num_chunks is 0 then
                #use as many chunks as needed for the document
                num_chunks = task_config.get('num_chunks')
                
                if task_config:
                    result[task] = self.llm_processor.process_text(
                        content,  
                        task_config,
                        num_chunks=num_chunks
                    )
                    
                    #llms return janky json
                    result[task] = clean_json(result[task])
                    
                    
                    
            except Exception as e:
                print(f"Error processing task '{task}': {str(e)}")
                result[task] = f"Error: {str(e)}"
            write_to_json(file_info['path'], result)
        return result if len(result) > 1 else None

def main():
    parser = argparse.ArgumentParser(description='Process documents in filesystem')
    parser.add_argument('--api-url', default='http://172.0.0.1:5001/api', help='the URL of the LLM API')
    parser.add_argument('--chunksize', default=1024, type=int, help='max tokens per chunk')
    parser.add_argument('--password', default='', help='server password')
    parser.add_argument('--model', default='llama3', help='llama3, cmdr, wizard, chatml, alpaca, mistral, phi3')
    parser.add_argument('directory', help='Directory to search')
    parser.add_argument('--recursive', action='store_true', help='Search recursively')
    parser.add_argument('--categories', nargs='+', help='document, spreadsheet, web, code, archive')
    parser.add_argument('--tasks', nargs='+', default=['info'], help='info, summarize, translate, interrogate, repeat, metadata, custom')
    parser.add_argument('--task-config', default='task_config.json', help='task_config.json')
    parser.add_argument('--write-json', action='store_true', help='Write to json')
    parser.add_argument('--output-file', default='results', help='json output-file')
    args = parser.parse_args()

            
    file_crawler = FileCrawler()
    file_list = file_crawler.crawl(args.directory, args.recursive, args.categories)
    llm_processor = LLMProcessor(args.api_url, args.password, args.model, args.chunksize)
    task_processor = TaskProcessor(llm_processor, args.task_config)
    results = task_processor.process_files(file_list, args.tasks)
    if args.write_json:
        write_to_json(args.output_file, results)
    total_files_processed = len(results)
    print(f"\nTotal files processed: {total_files_processed}")

if __name__ == "__main__":
    main()
