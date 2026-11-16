import json

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if "write_file" in line and ("views.py" in line):
            data = json.loads(line)
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                path = args.get("Path", "")
                if "apps" in str(path) and "views.py" in str(path):
                    content = args.get("Content", "")
                    print(f"Line {line_num}: write_file {path} len={len(content)}")
                    with open(r"scratch\recovered_full_views.py", "w", encoding="utf-8") as out:
                        out.write(content)
                    print("Wrote to scratch/recovered_full_views.py")

