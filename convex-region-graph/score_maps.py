"""Prepare class-1 data and score query priority with local Ollama.

Writes query_labeled_data.json and query_priority_scores.json. Legacy
scores.json and scoring_prompt.txt remain untouched for comparison.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

from prepare_scoring_data import ROOT, DEFAULT_CONFIG, prepare_file, digest

MODEL = 'qwen3:4b-instruct'
DEFAULT_PROMPT = ROOT / 'query_scoring_prompt.txt'
SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['scored', 'insufficient_data']},
        'score': {'anyOf': [{'type': 'integer', 'minimum': 0, 'maximum': 10}, {'type': 'null'}]},
        'reason': {'type': 'string', 'minLength': 1, 'maxLength': 320},
    },
    'required': ['status', 'score', 'reason'], 'additionalProperties': False,
}


def validate_answer(answer):
    if not isinstance(answer, dict) or set(answer) != set(SCHEMA['required']):
        raise ValueError('Response must contain exactly status, score and reason')
    if answer['status'] not in ('scored', 'insufficient_data'):
        raise ValueError('Unknown scoring status')
    if not isinstance(answer['reason'], str) or not answer['reason'].strip():
        raise ValueError('Missing explanation')
    if len(answer['reason']) > 320:
        raise ValueError('Explanation must contain at most 320 characters')
    score = answer['score']
    if answer['status'] == 'scored':
        if type(score) is not int or not 0 <= score <= 10:
            raise ValueError('Score must be an integer from 0 to 10')
    elif score is not None:
        raise ValueError('Insufficient data requires a null score')
    return answer


def ask_ollama(task, features, *, model=MODEL, prompt=None, base_url='http://localhost:11434'):
    payload = {'model': model, 'messages': [
        {'role': 'system', 'content': prompt if prompt is not None else DEFAULT_PROMPT.read_text()},
        {'role': 'user', 'content': json.dumps({'task': task, **features}, allow_nan=False)}],
        'format': SCHEMA, 'stream': False, 'options': {'temperature': 0, 'num_predict': 180}}
    request = Request(base_url.rstrip('/') + '/api/chat',
                      data=json.dumps(payload, allow_nan=False).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=600) as response:
        result = json.load(response)
    return validate_answer(json.loads(result['message']['content']))


def context_for(data):
    return {'map': data['map'], 'planning': data['planning'], 'query': data['query'],
            'sequences': data['sequences'],
            'retained_adjacency': [
                {'source': direction['source'], 'target': direction['target'], 'weight': direction['weight']}
                for edge in data['connections'] for direction in edge['directions']],
            'class1_label_rules': data['configuration']['label_rules'],
            'feature_definitions': data['configuration']['feature_definitions'],
            'pending_agreement': data['configuration']['pending_agreement'],
            'limitations': data['limitations']}


def atomic_save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def explanation_review_flags(answer, item, connection=False):
    """Flag possible unsupported label claims without altering model scores.

    This conservative text check is a review aid, not semantic verification.
    Python-computed labels remain the only authoritative labels.
    """
    reason = answer['reason'].lower()
    flags = []
    terms = {'junction': r'\bjunction\b', 'corridor': r'\bcorridor\b',
             'open': r'\bopen\b', 'dead_end': r'\bdead[- ]end\b',
             'pocket': r'\bpocket\b', 'narrow': r'\bnarrow\b',
             'critical': r'\bcritical\b', 'alternative_route': r'\balternative route\b'}
    for label, pattern in terms.items():
        for match in re.finditer(pattern, reason):
            prefix = reason[max(0, match.start()-45):match.start()]
            if re.search(r'\b(no|not|without|inactive|unavailable|missing)\b', prefix):
                continue
            evidence = item['memberships'].get(label)
            if evidence is None or evidence['active'] is not True:
                flags.append(f'Possible unsupported positive label claim: {label}')
                break
    if connection and not item['structural_features']['mandatory_on_all_start_goal_paths']:
        for match in re.finditer(r'\b(mandatory|unavoidable|required on all|every path)\b', reason):
            prefix = reason[max(0, match.start()-30):match.start()]
            if not re.search(r'\b(no|not|without)\b', prefix):
                flags.append('Possible all-path necessity claim not supported by the graph test')
                break
    return flags


def score_prepared(data, *, model=MODEL, prompt_path=DEFAULT_PROMPT,
                   output, resume=False, base_url='http://localhost:11434', request_fn=None):
    prompt_path = Path(prompt_path)
    prompt = prompt_path.read_text(encoding='utf-8')
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()
    provenance = {'prepared_data_sha256': fingerprint, 'prompt_sha256': digest(prompt_path),
                  'model': model, 'temperature': 0, 'base_url': base_url,
                  'response_schema': SCHEMA, 'num_predict': 180}
    result = {'schema': 'query-priority-scores/v1', 'map': data['map'], 'model': model,
              'score_meaning': 'query_specific_priority_not_local_geometric_suitability',
              'run': provenance, 'status': 'in_progress',
              'limitations': data['limitations'] + data['configuration']['pending_agreement'],
              'regions': [], 'edges': []}
    output = Path(output)
    if resume and output.exists():
        result = json.loads(output.read_text())
        if result.get('run') != provenance:
            raise ValueError('Cannot resume: model, input data, server, or prompt changed')
    context = context_for(data)
    by_id = {r['id']: r for r in data['regions']}
    tasks = [('regions', r['id'], 'query_region_priority', {'id': r['id']}, r)
             for r in data['regions']]
    tasks += [('edges', (e['source'], e['target']), 'query_connection_priority',
               {'source': e['source'], 'target': e['target']},
               {**e, 'endpoint_regions': [by_id[e['source']], by_id[e['target']]]})
              for e in data['connections']]
    call = request_fn or ask_ollama
    for collection, key, task, identity, item in tasks:
        def identity_key(record):
            return record['id'] if collection == 'regions' else (record['source'], record['target'])
        existing = [record for record in result[collection] if identity_key(record) == key]
        if existing:
            if len(existing) != 1:
                raise ValueError('Duplicate checkpoint item')
            validate_answer({k: existing[0][k] for k in SCHEMA['required']})
            continue
        print(f"{data['map']}: {task} {key}", flush=True)
        if data['query']['status'] != 'connected':
            answer = {'status': 'insufficient_data', 'score': None,
                      'reason': 'No start-goal sequence in the supplied query graph; priority is undefined.'}
        else:
            answer = validate_answer(call(task, {'context': context, 'item': item},
                                          model=model, prompt=prompt, base_url=base_url))
        result[collection].append({**identity, **answer})
        atomic_save(output, result)
    result['status'] = 'complete'
    targets = {r['id']: r for r in data['regions']}
    connections = {(e['source'], e['target']): e for e in data['connections']}
    for record in result['regions']:
        record['review_flags'] = explanation_review_flags(record, targets[record['id']])
    for record in result['edges']:
        record['review_flags'] = explanation_review_flags(
            record, connections[record['source'], record['target']], connection=True)
    result['review'] = {
        'calibration': 'provisional_requires_supervisor_agreement',
        'flagged_items': sum(bool(r['review_flags']) for r in result['regions'] + result['edges']),
        'note': 'Heuristic text flags require human review; they do not prove an error, '
                'change scores, modify labels, or reject graph elements.'}
    atomic_save(output, result)
    return result


def score_map(map_name, *, graph=None, config=DEFAULT_CONFIG, k=None,
              prepared_output=None, output=None, prompt=DEFAULT_PROMPT,
              model=MODEL, resume=False, prepare_only=False, base_url='http://localhost:11434'):
    graph = Path(graph or ROOT / 'research/data' / map_name / 'graph.json')
    prepared_output = Path(prepared_output or ROOT / 'outputs' / map_name / 'query_labeled_data.json')
    output = Path(output or ROOT / 'outputs' / map_name / 'query_priority_scores.json')
    protected = {graph.resolve(), Path(config).resolve(), Path(prompt).resolve(),
                 (ROOT / 'outputs' / map_name / 'scores.json').resolve()}
    if prepared_output.resolve() in protected or output.resolve() in protected or output.resolve() == prepared_output.resolve():
        raise ValueError('New artifacts must not overwrite graph, config, prompt, legacy scores, or each other')
    data = prepare_file(graph, config, k, map_name, prepared_output)
    print(f"Prepared {data['query']['returned_k']} sequences; saved {prepared_output}", flush=True)
    if prepare_only:
        return data
    return score_prepared(data, model=model, prompt_path=prompt, output=output,
                          resume=resume, base_url=base_url)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', required=True, choices=['hole', 'narrow', 'flappy', 'room'])
    parser.add_argument('--graph', type=Path, help='Explicit graph path; defaults to the prepared research graph')
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--k', type=int)
    parser.add_argument('--prepared-output', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--prompt', type=Path, default=DEFAULT_PROMPT)
    parser.add_argument('--model', default=MODEL)
    parser.add_argument('--base-url', default='http://localhost:11434')
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    score_map(args.map, graph=args.graph, config=args.config, k=args.k,
              prepared_output=args.prepared_output, output=args.output, prompt=args.prompt,
              model=args.model, resume=args.resume, prepare_only=args.prepare_only,
              base_url=args.base_url)


if __name__ == '__main__':
    main()
