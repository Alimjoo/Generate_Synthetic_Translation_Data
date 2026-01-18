import glob
import os

def merge_jsonl_files():
    # 1. Setup paths
    input_folder = 'out'
    output_filename = 'merged_uyghur_translations.jsonl'
    
    # 2. Find all .jsonl files in the 'out' folder
    # This creates a list of file paths like ['out/file1.jsonl', 'out/file2.jsonl', ...]
    search_path = os.path.join(input_folder, '*.jsonl')
    files = glob.glob(search_path)
    
    # Sort them by name so they merge in chronological order (based on your timestamps)
    files.sort()

    print(f"Found {len(files)} files to merge.")

    # 3. Create the new merged file
    with open(output_filename, 'w', encoding='utf-8') as outfile:
        for filename in files:
            print(f"Processing: {filename}")
            try:
                with open(filename, 'r', encoding='utf-8') as infile:
                    for line in infile:
                        # Write the line to the new file
                        outfile.write(line)
                        
                        # Safety check: Ensure the file ends with a newline 
                        # so the next file doesn't start on the same line.
                        if not line.endswith('\n'):
                            outfile.write('\n')
            except Exception as e:
                print(f"Error reading {filename}: {e}")

    print(f"\nSuccess! All files merged into: {output_filename}")

if __name__ == "__main__":
    merge_jsonl_files()
    
    