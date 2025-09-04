
import hashlib, json, time, os

def snapshot_hash(user_ids):
    j = json.dumps(sorted(list(user_ids)), ensure_ascii=False)
    return hashlib.sha256(j.encode()).hexdigest()

def write_audit(event_id, seed, dsl_json, sql, snapshot_hash_value, outdir='runs'):
    os.makedirs(outdir, exist_ok=True)
    rec = {
        'event_id': event_id,
        'seed': seed,
        'dsl': dsl_json,
        'sql': sql,
        'snapshot_hash': snapshot_hash_value,
        'ts': int(time.time())
    }
    path = os.path.join(outdir, f'audit_{rec["ts"]}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return path
