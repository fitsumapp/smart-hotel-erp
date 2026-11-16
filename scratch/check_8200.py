import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in range(8200, 8250):
            data = json.loads(line)
            tcs = data.get("tool_calls", [])
            for tc in tcs:
                name = tc.get("name")
                args = tc.get("args", {})
                print(f"Line {line_num}: {name} {args.get('Path')} len(Content)={len(args.get('Content',''))}")
                if "views.py" in str(args.get("Path", "")):
                    if name == "write_file":
                        with open("scratch/views_8200.py", "w", encoding="utf-8") as out:
                            out.write(args.get("Content", ""))
                        print("Saved views_8200.py!")

