import json

sub_transcript = r"C:\Users\hp\.gemini\antigravity\brain\46ebb571-3a44-4fc6-93cc-ed6ff1951634\.system_generated\logs\transcript_full.jsonl"

# Read baseline 4552
with open("scratch/recovered_write_4552.py", "r", encoding="utf-8") as f:
    code = f.read()

# Apply edits in exact order: 4571, 4573, 4579, 4583, 4743, 5122, 5126, 5301, 5625, 5813, 7557, 8075, 8077, 8177, 8199
edits_to_apply = [4571, 4573, 4579, 4583, 4743, 5122, 5126, 5301, 5625, 5813, 7557, 8199]

with open(sub_transcript, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if line_num in edits_to_apply:
            data = json.loads(line)
            for tc in data.get("tool_calls", []):
                args = tc.get("args", {})
                if "views.py" in str(args.get("Path", "")):
                    name = tc.get("name")
                    if name == "write_file" and args.get("Append"):
                        code += "\n" + args.get("Content", "")
                        print(f"Step {line_num}: Appended {len(args.get('Content', ''))} chars")
                    elif name == "edit_file":
                        target = args.get("Target", "")
                        repl = args.get("Replacement", "")
                        if target in code:
                            code = code.replace(target, repl, 1)
                            print(f"Step {line_num}: Replaced {len(target)} chars successfully")
                        else:
                            print(f"Step {line_num}: FAILED to find target!")

# Also check imports at the top:
# Need RequestForQuotation, RequestForQuotationItem, SupplierQuotation, SupplierQuotationItem
# and create_request_for_quotation, evaluate_quotation, evaluate_and_award_quotations, convert_awarded_quotations_to_purchase_orders, publish_request_for_quotation, close_request_for_quotation
# and serializers RequestForQuotationSerializer, RequestForQuotationItemSerializer, SupplierQuotationSerializer, SupplierQuotationItemSerializer

with open("apps/inventory/views.py", "w", encoding="utf-8") as out:
    out.write(code)

print("Saved to apps/inventory/views.py, total lines:", len(code.splitlines()))

