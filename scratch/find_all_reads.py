import json

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

read_ranges = []
with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if "read_file" in line and ("apps\\inventory\\views.py" in line or "apps/inventory/views.py" in line):
            data = json.loads(line)
            tool_calls = data.get("tool_calls", [])
            for tc in tool_calls:
                args = tc.get("args", {})
                if "views.py" in args.get("Path", ""):
                    read_ranges.append((line_num, args.get("StartLine"), args.get("EndLine")))

print("Read calls found:", len(read_ranges))
for r in read_ranges:
    print(r)

