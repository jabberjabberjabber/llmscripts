import json
import os

def rename_files(json_path):
    # Read the JSON file
    with open(json_path, 'r') as f:
        data = json.load(f)

    # Create a new dictionary to store updated data
    updated_data = {}

    # Iterate through each file in the JSON
    for old_filename, file_info in data.items():
        # Check if the file_info is nested (for images)
        if 'Metadata' in file_info:
            file_info = file_info['Metadata']

        full_path = file_info.get('FullPath')
        proposed_filename = file_info.get('ProposedFilename')
        
        if not full_path or not proposed_filename:
            print(f"Skipping {old_filename}: missing FullPath or ProposedFilename")
            updated_data[old_filename] = data[old_filename]
            continue

        # Get the directory, original extension, and new filename
        directory = os.path.dirname(full_path)
        original_extension = os.path.splitext(full_path)[1]
        new_filename = os.path.splitext(proposed_filename)[0] + original_extension

        # Construct the new full path
        new_full_path = os.path.join(directory, new_filename)

        # Rename the file
        try:
            if os.path.exists(full_path):
                os.rename(full_path, new_full_path)
                print(f"Renamed: {full_path} -> {new_full_path}")

                # Update the file info
                file_info['PreviousName'] = old_filename
                file_info['FullPath'] = new_full_path
                file_info['File'] = new_filename

                # If it's an image, update the nested structure
                if 'Metadata' in data[old_filename]:
                    updated_data[new_filename] = data[old_filename].copy()
                    updated_data[new_filename]['Metadata'] = file_info
                else:
                    updated_data[new_filename] = file_info
            else:
                print(f"File not found: {full_path}")
                updated_data[old_filename] = data[old_filename]

        except Exception as e:
            print(f"Error processing {full_path}: {str(e)}")
            updated_data[old_filename] = data[old_filename]

    # Write the updated JSON back to the file
    with open(json_path, 'w') as f:
        json.dump(updated_data, f, indent=2)

    print("JSON file updated successfully.")

# Usage
json_path = 'file_metadata.json'  # Replace with your JSON file path
rename_files(json_path)
