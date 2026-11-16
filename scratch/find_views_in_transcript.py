import json
import re

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

found_steps = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if "apps/inventory/views.py" in line or "apps\\\\inventory\\\\views.py" in line:
            data = json.loads(line)
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                name = tc.get("name")
                args = tc.get("args", {})
                path = args.get("Path", "")
                if "views.py" in str(path):
                    found_steps.append((line_num, name, path, len(args.get("Content", "")), len(args.get("Replacement", ""))))

print(f"Found {len(found_steps)} relevant tool calls:")
for s in found_steps:
    print(s)

