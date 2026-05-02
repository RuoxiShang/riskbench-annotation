"""Extract the 15 claude-sonnet J-flagged records for verification review."""
import json
from pathlib import Path

# Source files with J tags
SOURCES = [
    '/tmp/refuse_axis_analysis.json',    # Agent 7, 10 sonnet faults
    '/tmp/final_results.jsonl',          # Agent 4, 5 sonnet faults
]

# Extract scenario_ids tagged J with claude-sonnet fault
sonnet_j_ids = []

for fp in SOURCES:
    with open(fp) as f:
        content = f.read()
    try:
        data = json.loads(content)
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get('records', [data])
        else:
            records = []
    except json.JSONDecodeError:
        records = [json.loads(l) for l in content.splitlines() if l.strip()]

    for r in records:
        if 'J' not in str(r.get('tag', '')):
            continue
        jfs = r.get('judge_faults', [])
        for jf in jfs:
            if 'sonnet' in str(jf).lower():
                sonnet_j_ids.append({
                    'scenario_id': r.get('scenario_id'),
                    'agent_model': r.get('agent_model'),
                    'pattern': r.get('pattern'),
                    'votes': r.get('votes'),
                    'source_file': fp,
                    'original_tag': r.get('tag'),
                    'original_judge_fault': jf,
                    'original_evidence': r.get('evidence_note', ''),
                })
                break

print(f"Found {len(sonnet_j_ids)} claude-sonnet J-flagged records")
for s in sonnet_j_ids:
    print(f"  {s['scenario_id']} | agent={s['agent_model']} | pattern={s['pattern']} | tag={s['original_tag']}")

# Now fetch the FULL record (agent action + all 4 judge rationales) for each from the source review files
ids_to_find = {(s['scenario_id'], s['agent_model']) for s in sonnet_j_ids}

full_records = []
for source_fp in ['/tmp/action_2_2_review.jsonl', '/tmp/action_2_1_1_review.jsonl', '/tmp/action_1_1_1_1_review.jsonl']:
    with open(source_fp) as f:
        for line in f:
            rec = json.loads(line)
            key = (rec.get('scenario_id'), rec.get('agent_model'))
            if key in ids_to_find:
                full_records.append(rec)

print(f"\nFetched {len(full_records)} full records")

# Merge with original J-tag info for reviewer context
id_to_orig = {(s['scenario_id'], s['agent_model']): s for s in sonnet_j_ids}
out = []
for rec in full_records:
    key = (rec.get('scenario_id'), rec.get('agent_model'))
    orig = id_to_orig.get(key, {})
    rec['_original_j_flag'] = {
        'source': orig.get('source_file'),
        'judge_fault': orig.get('original_judge_fault'),
        'evidence_note': orig.get('original_evidence'),
    }
    out.append(rec)

with open('/tmp/sonnet_j_verification_set.jsonl', 'w') as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')

print(f"Wrote {len(out)} records to /tmp/sonnet_j_verification_set.jsonl")
