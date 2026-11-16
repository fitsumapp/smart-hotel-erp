import json

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num == 2958:
            data = json.loads(line)
            tool_calls = data.get("tool_calls", [])
            print("Step 2958 tool calls:", len(tool_calls))
            for tc in tool_calls:
                print(tc.get("name"), tc.get("args"))
        elif line_num == 2959:
            data = json.loads(line)
            content = data.get("content", "")
            print("Step 2959 content length:", len(content))
            with open("scratch/step_2959_content.txt", "w", encoding="utf-8") as out:
                out.write(content)
            print("Wrote scratch/step_2959_content.txt")

