import json
import re

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

candidate_lines = [70, 72, 76, 82, 84, 91, 96, 126, 153, 165, 176, 180, 181, 182, 325, 518, 522, 526, 530, 568, 571, 572, 573, 575, 577, 587, 589, 615, 617, 619]

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in candidate_lines:
            data = json.loads(line)
            # check tool calls
            tcs = data.get("tool_calls", [])
            content = data.get("content", "")
            for tc in tcs:
                name = tc.get("name")
                args = tc.get("args", {})
                print(f"Line {line_num} tool: {name} {args.get('Path')} len(Content)={len(args.get('Content',''))} len(Replacement)={len(args.get('Replacement',''))}")
            if "Showing lines" in content or "class " in content:
                print(f"Line {line_num} content snippet: {content[:100]}... len={len(content)}")

