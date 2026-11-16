import json
import re

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

matches = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if re.search(r'apps[\\/]+inventory[\\/]+views\.py', line, re.IGNORECASE):
            matches.append(line_num)

print(f"Total matching lines: {len(matches)}")
print(matches[:30])

