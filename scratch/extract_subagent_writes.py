import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in (4552, 5625):
            data = json.loads(line)
            tcs = data.get("tool_calls", [])
            for tc in tcs:
                args = tc.get("args", {})
                p = args.get("Path", "")
                c = args.get("Content", "")
                print(f"Line {line_num}: Path={p} len={len(c)}")
                fname = f"scratch/recovered_write_{line_num}.py"
                with open(fname, "w", encoding="utf-8") as out:
                    out.write(c)
                print(f"Saved to {fname}")

