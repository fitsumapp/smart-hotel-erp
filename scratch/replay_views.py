import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

file_content = None

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num == 4552:
            data = json.loads(line)
            tcs = data.get("tool_calls", [])
            file_content = tcs[0]["args"]["Content"]
            print(f"Base loaded at 4552: len={len(file_content)}")
        elif file_content is not None and ("edit_file" in line or "write_file" in line) and "views.py" in line:
            data = json.loads(line)
            tcs = data.get("tool_calls", [])
            for tc in tcs:
                name = tc.get("name")
                args = tc.get("args", {})
                p = str(args.get("Path", ""))
                if "apps" in p and "views.py" in p and "inventory" in p:
                    if name == "write_file":
                        # check if it replaced the whole file or something else
                        c = args.get("Content", "")
                        print(f"Line {line_num} write_file: len={len(c)}")
                        # Note: line 5625 had len 6632, let's see what it was
                    elif name == "edit_file":
                        target = args.get("Target", "")
                        repl = args.get("Replacement", "")
                        if target in file_content:
                            file_content = file_content.replace(target, repl)
                            print(f"Line {line_num} edit_file success: len now {len(file_content)}")
                        else:
                            print(f"Line {line_num} edit_file target NOT found: target[:50]={repr(target[:50])}")

with open(r"scratch\replayed_views.py", "w", encoding="utf-8") as out:
    out.write(file_content)

print("Saved replayed_views.py, total lines:", len(file_content.splitlines()))

