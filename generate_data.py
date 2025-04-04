import re
import json
from pathlib import Path

def parse_book_data():
    try:
        # Read the script file
        script_path = Path('./sourceScript.js')
        with script_path.open('r', encoding='utf-8') as f:
            script_content = f.read()

        # Result dictionary with nested structure
        result = {}

        # Split into conditions and process each
        conditions = [c.strip() for c in script_content.split('else if')]

        for condition in conditions:
            # Extract class
            class_match = re.search(r'tclass\.value\s*==\s*(\d+)', condition)
            class_value = class_match.group(1) if class_match else None

            # Extract subject
            subject_match = re.search(r'tsubject\.options\[sind\]\.text\s*==\s*"([^"]+)"', condition)
            subject = subject_match.group(1) if subject_match else None

            # Skip if no class or subject, or if subject is placeholder
            if not class_value or not subject or subject == "..Select Subject..":
                continue

            # Initialize nested structure
            if class_value not in result:
                result[class_value] = {}
            if subject not in result[class_value]:
                result[class_value][subject] = []

            # Extract all book options
            book_pattern = r'tbook\.options\[(\d+)\]\.text\s*=\s*"([^"]+)";[\s\S]*?tbook\.options\[\1\]\.value\s*=\s*"([^"]+)"'
            book_matches = re.finditer(book_pattern, condition)

            for match in book_matches:
                index, title, full_code = match.groups()

                # Skip placeholder and empty titles
                if title == "..Select Book Title.." or not title.strip():
                    continue

                # Parse code and chapters from URL
                code_match = re.match(r'textbook\.php\?([a-zA-Z0-9]+)=(\d+-\d+)', full_code)
                code = code_match.group(1) if code_match else full_code
                chapters = code_match.group(2) if code_match else ""

                # Add book data
                result[class_value][subject].append({
                    "text": title,
                    "code": code,
                    "chapters": chapters
                })

        # Write to JSON file
        output_path = Path('./data.json')
        with output_path.open('w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print("Successfully parsed sourceScript.js and updated data.json")

    except Exception as e:
        print(f"Error processing files: {str(e)}")

if __name__ == "__main__":
    parse_book_data()