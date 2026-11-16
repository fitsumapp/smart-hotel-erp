import os
import glob
import json

brain_dir = r"C:\Users\hp\.gemini\antigravity\brain"

pattern = os.path.join(brain_dir, "*", ".system_generated", "logs", "transcript_full.jsonl")
files = glob.glob(pattern)
print(f"Found {len(files)} transcript_full files.")

found_writes = []
for fpath in files:
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                if '"write_file"' in line and 'apps' in line and 'views.py' in line:
                    data = json.loads(line)
                    tcs = data.get("tool_calls", [])
                    for tc in tcs:
                        args = tc.get("args", {})
                        p = str(args.get("Path", ""))
                        if "apps" in p and "views.py" in p:
                            c = args.get("Content", "")
                            found_writes.append((fpath, line_num, p, len(c)))
                            print(f"Found write_file in {fpath} line {line_num}: len={len(c)}")
                            with open(r"scratch\recovered_views_from_subagent.py", "w", encoding="utf-8") as out:
                                out.write(c)
                            print("Wrote to scratch/recovered_views_from_subagent.py!")
    except Exception as e:
        pass

print(f"Total writes found: {len(found_writes)}")

