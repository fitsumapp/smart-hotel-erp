import json

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in (2961, 2962, 2963, 2964, 2965):
            data = json.loads(line)
            content = data.get("content", "")
            if "Showing lines" in content:
                print(f"Line {line_num}: length {len(content)}")
                # save to scratch/recovered_views_chunk.txt
                with open(r"scratch\recovered_views_chunk.txt", "w", encoding="utf-8") as out:
                    out.write(content)
                print("Saved content from line", line_num)
                break

