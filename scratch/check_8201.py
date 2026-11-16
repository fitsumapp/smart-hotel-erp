import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in (8198, 8199, 8200, 8201, 8202):
            data = json.loads(line)
            print(f"Line {line_num}: type={data.get('type')}")
            for tc in data.get("tool_calls", []):
                print("  Tool call:", tc.get("name"), tc.get("args"))
            if data.get("content"):
                print("  Content preview:", repr(data.get("content")[:300]))

