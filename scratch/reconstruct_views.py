import json
import re

transcript_path = r"C:\Users\hp\.gemini\antigravity\brain\1f1b0a59-f505-49c7-8e24-a8604d2b4051\.system_generated\logs\transcript_full.jsonl"

chunks = {}

steps_to_extract = [
    574, 576, 578, 588, 590, 616, 618, 620, 622, 626,
    853, 857, 1194, 1258, 1260, 1331, 1333, 1337,
    2299, 2794, 2824, 2826, 2959, 2963, 2965, 3001, 3005
]

line_dict = {}

with open(transcript_path, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in steps_to_extract:
            data = json.loads(line)
            content = data.get("content", "")
            # extract "Showing lines X-Y of Z"
            match = re.search(r"Showing lines (\d+)-(\d+) of (\d+)", content)
            if match:
                start_line = int(match.group(1))
                end_line = int(match.group(2))
                # lines are in format "123: code"
                for code_line in content.split("\n"):
                    m_code = re.match(r"^(\d+):\s?(.*)$", code_line)
                    if m_code:
                        num = int(m_code.group(1))
                        text = m_code.group(2)
                        line_dict[num] = text

print(f"Total unique line numbers recovered: {len(line_dict)}")
if line_dict:
    min_l, max_l = min(line_dict.keys()), max(line_dict.keys())
    print(f"Range: {min_l} to {max_l}")
    missing = [i for i in range(1, max_l + 1) if i not in line_dict]
    print(f"Missing lines count: {len(missing)}")
    if missing:
        # group missing ranges
        import itertools
        from operator import itemgetter
        ranges = []
        for k, g in itertools.groupby(enumerate(missing), lambda ix: ix[0] - ix[1]):
            group = list(map(itemgetter(1), g))
            ranges.append((group[0], group[-1]))
        print("Missing line ranges:", ranges)

