import os
import re

SRC_DIR = r"c:\Users\BAB AL SAFA\Desktop\Smart Hotel ERP\hotel-frontend\src"

def process_js_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    
    # Check if file has any 127.0.0.1 URLs
    if "http://127.0.0.1:8000" not in content:
        return

    # Determine relative path to apiConfig.js
    file_dir = os.path.dirname(filepath)
    rel_path = os.path.relpath(SRC_DIR, file_dir).replace('\\', '/')
    if rel_path == '.':
        api_config_import = "import { API_BASE_URL, BASE_URL } from './apiConfig';"
    else:
        api_config_import = f"import {{ API_BASE_URL, BASE_URL }} from '{rel_path}/apiConfig';"

    # Add the import statement just after the last 'import' statement
    import_index = content.rfind("import ")
    if import_index != -1:
        end_of_line = content.find('\n', import_index)
        content = content[:end_of_line + 1] + api_config_import + "\n" + content[end_of_line + 1:]
    else:
        content = api_config_import + "\n\n" + content

    # Replace specific /api/ endpoint usages
    # e.g., 'http://127.0.0.1:8000/api/some/path' -> `${API_BASE_URL}/some/path`
    content = re.sub(r"['\"]http://127\.0\.0\.1:8000/api/([^'\"]*)['\"]", r"`${API_BASE_URL}/\1`", content)
    
    # Replace plain occurrences
    content = re.sub(r"['\"]http://127\.0\.0\.1:8000/api['\"]", r"API_BASE_URL", content)

    # Replace media / base usages
    content = re.sub(r"['\"]http://127\.0\.0\.1:8000/media/([^'\"]*)['\"]", r"`${BASE_URL}/media/\1`", content)
    content = re.sub(r"['\"]http://127\.0\.0\.1:8000/?([^'\"]*)['\"]", r"`${BASE_URL}/\1`", content)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")

for root, dirs, files in os.walk(SRC_DIR):
    for filename in files:
        if filename.endswith(".js") or filename.endswith(".jsx"):
            filepath = os.path.join(root, filename)
            process_js_file(filepath)

print("✅ Frontend API URLs updated to use Dynamic Subdomains.")
