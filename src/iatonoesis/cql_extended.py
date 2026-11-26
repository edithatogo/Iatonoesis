"""Frozen public CQL references and bounded six-frame inference (not clinical admission)."""
import argparse
import hashlib
import json
import operator
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

REVISION = '1991335e7ad490a8db88a05dd7f03dc3eecbda6d'
SOURCES = {
    'CqlComparisonOperatorsTest.xml': '67eb1cee39deb483a1eccd4efa1cdd949c5b200f',
    'CqlNullologicalOperatorsTest.xml': '5af5c10d1b733178f46d2716befe919356edf100',
    'CqlArithmeticFunctionsTest.xml': '3e580c82e7d0d7f13132948d64fd7f919fe76fb2',
}
MODELS = {
    'HuggingFaceTB/SmolLM2-360M-Instruct': ('c15f933c73438218a2bc078446c513173cc4f06a', 'e6bffe7435d7ddc10fd3b9a9efd429dafbacb1cb17015fb5562664e7532bf86e'),
    'Qwen/Qwen2.5-0.5B-Instruct': ('eaa56b503cc0a8a4d15de1dd8bd2a7e95a716be2', 'fdf756fa7fcbe7404d5c60e26bff1a0c8b8aa1f72ced49e7dd0210fe288fb7fe'),
}
FRAMES = {
    'F01': 'Evaluate the given CQL expression directly.',
    'F02': 'Ground the answer in the literal operands and operators actually present; do not assume missing evidence.',
    'F03': 'Account for each atomic condition and the composition of conditions before choosing the result.',
    'F04': 'Distinguish true from false and unknown; consider what would disconfirm each alternative.',
    'F05': 'Consider comparison boundaries and possible counterexamples; then evaluate the original expression, not a modified one.',
    'F06': 'Evaluate only when supported by the expression and CQL semantics; abstain when you cannot determine the result.',
}
LABELS = ('TRUE', 'FALSE', 'NULL', 'ABSTAIN', 'INVALID')


def git_blob(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()


def parse_suite(raw, suite):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('unexpected XML declaration')
    root = ET.fromstring(raw)
    rows, seen = [], set()
    for group in root.findall('.//{*}group'):
        for test in group.findall('{*}test'):
            key = f"{suite}/{group.attrib.get('name', '')}/{test.attrib.get('name', '')}"
            if key in seen:
                raise ValueError('duplicate reference identity')
            seen.add(key)
            expr = test.find('{*}expression')
            out = test.find('{*}output')
            expression = ''.join(expr.itertext()).strip() if expr is not None else ''
            literal = ''.join(out.itertext()).strip() if out is not None else ''
            row = dict(id=key, expression=expression, expected_literal=literal)
            if expr is not None and expr.attrib.get('invalid', '').lower() in ('true', '1'):
                status = 'declared_invalid'
            elif not expression or out is None or not literal:
                status = 'missing_reference'
            elif re.search(r'\b(?:\d+[lL]|Long)\b', expression):
                status = 'unsupported_long'
            elif re.search(r'\b(?:Today|Now|TimeOfDay)\s*\(', expression, re.I):
                status = 'clock_dependent'
            elif len(out) or not re.fullmatch(r'true|false|null|[+-]?\d+', literal):
                status = 'unsupported_reference_type'
            else:
                expected = {'true': True, 'false': False, 'null': None}[literal] if literal in ('true', 'false', 'null') else int(literal)
                if type(expected) is int and abs(expected) > 2**53-1:
                    status = 'unsupported_reference_type'
                else:
                    status = 'eligible'
                    row['expected'] = expected
            row['status'] = status
            rows.append(row)
    if not rows:
        raise ValueError('empty reference suite')
    return rows


def mutations():
    specs = [('eq', '=', operator.eq, '!=', operator.ne),
             ('ne', '!=', operator.ne, '=', operator.eq),
             ('lt', '<', operator.lt, '>', operator.gt),
             ('le', '<=', operator.le, '>=', operator.ge),
             ('gt', '>', operator.gt, '<', operator.lt),
             ('ge', '>=', operator.ge, '<=', operator.le)]
    rows, groups = [], []
    for name, op, fn, rev, revfn in specs:
        variants = [('base', op, fn, 2), ('minus_one', op, fn, 1),
                    ('plus_one', op, fn, 3), ('reversed', rev, revfn, 2)]
        cases = []
        for x in (1, 2, 3):
            ids = {}
            for v, symbol, f, t in variants:
                key = f'mutation_{name}_{x}_{v}'
                ids[v] = key
                rows.append(dict(id=key, expression=f'{x} {symbol} {t}', expected=f(x, t), status='eligible'))
            cases.append(ids)
        groups.append(dict(family=name, cases=cases, variants=[v[0] for v in variants]))
    return rows, groups


def label(value):
    if value is True:
        return 'TRUE'
    if value is False:
        return 'FALSE'
    if value is None:
        return 'NULL'
    raise ValueError('non-Boolean prompt reference')


def prompt_sample(cases):
    by_label = {k: [] for k in LABELS[:3]}
    for row in cases:
        if row['status'] == 'eligible' and (row['expected'] is None or type(row['expected']) is bool):
            by_label[label(row['expected'])].append(row)
    n = min(8, *(len(v) for v in by_label.values()))
    return [r for k in LABELS[:3] for r in sorted(by_label[k], key=lambda x: (hashlib.sha256(x['id'].encode()).hexdigest(), x['id']))[:n]]


def prompt(frame, expression):
    return (FRAMES[frame] + '\nClinical Quality Language (CQL), formal expression only. '
            'Use three-valued logic. NULL is a result, not abstention. '
            'Return exactly one uppercase label: TRUE, FALSE, NULL, or ABSTAIN. No explanation.\n'
            + 'Expression: ' + expression)


def parse_answer(answer):
    answer = answer.strip()
    return answer if answer in LABELS[:4] else 'INVALID'


def score(refs, predictions):
    if set(predictions) != {r['id'] for r in refs} or len(predictions) != len(refs):
        raise ValueError('prediction membership mismatch')
    confusion = {k: dict.fromkeys(LABELS, 0) for k in LABELS[:3]}
    for r in refs:
        confusion[label(r['expected'])][predictions[r['id']]] += 1
    correct = sum(confusion[k][k] for k in confusion)
    abstentions = sum(c['ABSTAIN'] for c in confusion.values())
    invalid = sum(c['INVALID'] for c in confusion.values())
    decided = len(refs) - abstentions - invalid
    return dict(total=len(refs), correct=correct, decided=decided, abstentions=abstentions,
                invalid=invalid, false_true=confusion['FALSE']['TRUE']+confusion['NULL']['TRUE'],
                false_true_denominator=sum(sum(confusion[k].values()) for k in ('FALSE','NULL')),
                confusion=confusion)


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def freeze(xml_dir, output_dir):
    rows, source_sha = [], {}
    for filename, blob in SOURCES.items():
        raw = (xml_dir / filename).read_bytes()
        if git_blob(raw) != blob:
            raise ValueError('source Git blob mismatch')
        rows.extend(parse_suite(raw, Path(filename).stem))
        source_sha[filename] = hashlib.sha256(raw).hexdigest()
    refs = [r for r in rows if r['status'] == 'eligible']
    sample = prompt_sample(rows)
    if not sample:
        raise ValueError('no balanced prompt sample')
    authored, groups = mutations()
    # Use fresh opaque case identifiers in ELM and maintain a separate mapping.
    for i, row in enumerate(refs):
        row['elm_id'] = f'upstream_{i:04d}'
    entries = [f'  "{r["elm_id"]}": Tuple{{ expression: {r["expression"]} }}' for r in refs]
    entries += [f'  "{r["id"]}": Tuple{{ expression: {r["expression"]} }}' for r in authored]
    cql = "library IatonoesisExtendedCases version '1.0.0'\nusing QUICK version '3.3.0'\ncontext Patient\n\ndefine \"Cases\": Tuple{\n" + ',\n'.join(entries) + '\n}\n'
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/'IatonoesisExtendedCases.cql').write_text(cql)
    write_json(output_dir/'freeze.json', dict(upstream_revision=REVISION, sources=source_sha,
               all_rows=rows, statuses=dict(Counter(r['status'] for r in rows)), mutations=authored,
               groups=groups, prompt_sample=sample,
               cql_sha256=hashlib.sha256(cql.encode()).hexdigest(), frames=FRAMES))


def run_models(frozen, output):
    import torch
    from huggingface_hub import HfApi, snapshot_download
    from transformers import AutoModelForCausalLM, AutoTokenizer

    torch.set_num_threads(2)
    torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    refs = frozen['prompt_sample']
    receipts = {}
    for repo, (revision, digest) in MODELS.items():
        info = HfApi().model_info(repo, revision=revision, files_metadata=True)
        weights = next((s for s in info.siblings if s.rfilename == 'model.safetensors'), None)
        if (info.sha != revision or info.card_data is None or info.card_data.license != 'apache-2.0'
                or weights is None or weights.size is None or weights.size > 1_200_000_000):
            raise ValueError('model admission gate')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(snapshot_download(repo, revision=revision, local_dir=tmp, allow_patterns=[
                'model.safetensors', 'config.json', 'generation_config.json', 'tokenizer.json',
                'tokenizer_config.json', 'special_tokens_map.json', 'vocab.json', 'merges.txt', 'added_tokens.json']))
            with (root/'model.safetensors').open('rb') as fh:
                actual = hashlib.file_digest(fh, 'sha256').hexdigest()
            if actual != digest:
                raise ValueError('model weight digest mismatch')
            token = AutoTokenizer.from_pretrained(root, local_files_only=True, trust_remote_code=False, padding_side='left')
            if token.pad_token_id is None:
                token.pad_token = token.eos_token
            model = AutoModelForCausalLM.from_pretrained(root, local_files_only=True, trust_remote_code=False, use_safetensors=True).eval()
            result = dict(revision=revision, weight_sha256=actual,
                          config_digests={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in root.iterdir() if p.is_file() and p.name != 'model.safetensors'},
                          frames={})
            for frame in FRAMES:
                predictions, counts = {}, [0, 0]
                start = time.monotonic()
                for i in range(0, len(refs), 4):
                    batch = refs[i:i+4]
                    strings = [token.apply_chat_template([{'role':'user','content':prompt(frame,r['expression'])}],
                               tokenize=False, add_generation_prompt=True) for r in batch]
                    inputs = token(strings, padding=True, return_tensors='pt', add_special_tokens=False)
                    if inputs['input_ids'].shape[1] > 512:
                        raise ValueError('prompt exceeds frozen input cap')
                    counts[0] += int(inputs['attention_mask'].sum())
                    with torch.inference_mode():
                        generated = model.generate(**inputs, do_sample=False, max_new_tokens=12,
                                                   pad_token_id=token.pad_token_id)
                    suffix = generated[:, inputs['input_ids'].shape[1]:]
                    for row, ids, decoded in zip(batch, suffix, token.batch_decode(suffix, skip_special_tokens=True)):
                        counts[1] += sum(int(x) != token.pad_token_id for x in ids)
                        predictions[row['id']] = parse_answer(decoded)
                result['frames'][frame] = dict(**score(refs, predictions), predictions=predictions,
                    input_tokens=counts[0], output_nonpad_tokens=counts[1], runtime_seconds=round(time.monotonic()-start,3))
            receipts[repo] = result
            del model, token
        write_json(output, dict(scope='exploratory_public_formal_reference_only', models=receipts))
    return receipts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['freeze','frame'])
    ap.add_argument('source', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    if args.mode == 'freeze':
        freeze(args.source,args.output)
    else:
        run_models(json.loads(args.source.read_text()), args.output)


if __name__ == '__main__':
    main()
