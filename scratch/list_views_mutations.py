import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num > 4552 and ("edit_file" in line or "write_file" in line) and "apps" in line and "inventory" in line and "views.py" in line:
            data = json.loads(line)
            for tc in data.get("tool_calls", []):
                p = tc.get("args", {}).get("Path", "")
                if "views.py" in p and "inventory" in p:
                    print(f"Line {line_num}: {tc.get('name')} append={tc.get('args', {}).get('Append')} target_len={len(tc.get('args', {}).get('Target', ''))} repl_len={len(tc.get('args', {}).get('Replacement', ''))}")
                    target = tc.get("args", {}).get("Target", "")
                    repl = tc.get("args", {}).get("Replacement", "")
                    print(f"  Target preview: {repr(target[:60])}")
                    print(f"  Repl preview: {repr(repl[:60])}")

