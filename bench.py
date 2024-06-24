import time
import os
import json
from utils import APIHandler, NLPProcessor, FileHandler

def time_operation(operation, *args, **kwargs):
    start = time.time()
    result = operation(*args, **kwargs)
    end = time.time()
    return result, end - start

def test_pipeline(directory, api_handler):
    results = {}
    total_start = time.time()

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            file_results = {"file_path": file_path}

            file_content, file_read_time = time_operation(FileHandler.read_file, file_path)
            file_results["file_read_time"] = file_read_time

            if file_content:
                summary, summary_time = time_operation(api_handler.summarize, file_content)
                file_results["summary_time"] = summary_time
                file_results["summary_result"] = summary

            results[file] = file_results

    total_time = time.time() - total_start
    results["total_time"] = total_time

    return results

def main():
    test_directory = "c:/tools/test"
    api_handler = APIHandler('http://172.16.0.219:5001/api', 'poop')
    nlp_processor = NLPProcessor(api_handler)
    
    results = test_pipeline(test_directory, api_handler)
    
    with open("test_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
