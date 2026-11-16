import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

edits = []
with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if ("edit_file" in line or "write_file" in line) and "views.py" in line:
            data = json.loads(line)
            tcs = data.get("tool_calls", [])
            for tc in tcs:
                name = tc.get("name")
                args = tc.get("args", {})
                if "views.py" in str(args.get("Path", "")):
                    edits.append((line_num, name, args.get("Path"), len(args.get("Target", "")), len(args.get("Replacement", "")), len(args.get("Content", ""))))

print(f"Found {len(edits)} mutations:")
for e in edits:
    print(e)

