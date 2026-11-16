import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

with open(r"scratch\recovered_write_4552.py", "r", encoding="utf-8") as f:
    content = f.read()

lines_to_replay = [4571, 4573, 4579, 4583, 4743, 5122, 5126, 5301, 5625, 5813, 7557, 8075, 8077, 8081, 8177, 8183, 8191, 8193, 8195, 8199]

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in lines_to_replay:
            data = json.loads(line)
            for tc in data.get("tool_calls", []):
                name = tc.get("name")
                args = tc.get("args", {})
                p = str(args.get("Path", ""))
                if "views.py" in p and "inventory" in p:
                    if name == "write_file" and args.get("Append"):
                        content += "\n" + args.get("Content", "")
                        print(f"Line {line_num}: Appended {len(args.get('Content', ''))} chars")
                    elif name == "edit_file":
                        target = args.get("Target", "")
                        repl = args.get("Replacement", "")
                        if target in content:
                            content = content.replace(target, repl)
                            print(f"Line {line_num}: Replaced {len(target)} -> {len(repl)} chars")
                        else:
                            # Try normalizing line endings if needed
                            t_crlf = target.replace("\r\n", "\n")
                            c_crlf = content.replace("\r\n", "\n")
                            if t_crlf in c_crlf:
                                content = c_crlf.replace(t_crlf, repl.replace("\r\n", "\n"))
                                print(f"Line {line_num}: Replaced with normalized endings")
                            else:
                                print(f"Line {line_num}: ERROR - target not found!")
                                print("Target was:", repr(target[:80]))

with open(r"scratch\perfect_restored_views.py", "w", encoding="utf-8") as out:
    out.write(content)

print(f"Done! Final perfect_restored_views.py has {len(content.splitlines())} lines.")

