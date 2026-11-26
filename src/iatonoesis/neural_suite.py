"""Exploratory small CPU neural and guarded hybrid comparisons on exposed synthetic cases."""
import argparse
import copy
import json
import time
from pathlib import Path

import torch
from torch import nn

from . import core_suite as core
from .run_contracts import canonical_sha256, validate_experiment
from .runner import paired_f1_interval, run_experiment

SEQUENCE = {'E04', 'E17', 'E22'}
RANK = {'E02', 'E13'}


class FeatureNet(nn.Module):
    def __init__(self, size, outputs, sequence=False):
        super().__init__()
        self.sequence = sequence
        if sequence:
            self.embedding = nn.Embedding(size, 16, padding_idx=0)
            self.gru = nn.GRU(16, 24, batch_first=True)
            self.head = nn.Linear(24, outputs)
        else:
            self.head = nn.Sequential(nn.Linear(size, 32), nn.ReLU(), nn.Linear(32, outputs))

    def forward(self, x):
        if self.sequence:
            h, _ = self.gru(self.embedding(x))
            index = (x.ne(0).sum(1) - 1).clamp(min=0)
            return self.head(h[torch.arange(len(x)), index])
        return self.head(x)


class GraphNet(nn.Module):
    def __init__(self, outputs, messages=True):
        super().__init__()
        self.messages = messages
        self.encoder = nn.Linear(2, 24)
        self.update = nn.Linear(48, 24)
        self.head = nn.Linear(24, outputs)

    def forward(self, graph):
        x, adj = graph
        h = self.encoder(x).relu()
        for _ in range(4):
            message = adj @ h if self.messages else torch.zeros_like(h)
            h = self.update(torch.cat((h, message), dim=-1)).relu()
        return self.head((h * x[:, :, 1:2]).sum(1))


def graph_tensor(inputs):
    x = torch.zeros((len(inputs), 16, 2))
    adj = torch.zeros((len(inputs), 16, 16))
    for i, inp in enumerate(inputs):
        x[i, inp['start'], 0] = 1
        x[i, inp['end'], 1] = 1
        for a, b in inp['edges']:
            adj[i, b, a] = 1
    return x, adj


def groups(key, inp):
    if key == 'E02':
        return list(core.layout_candidates(inp))
    if key == 'E13':
        return [[(c['id'], core.rank_features(inp, c)) for c in inp['candidates']]]
    raise ValueError('not a ranking task')


def _same(a, b):
    if a is None or b is None:
        return a is b
    return sorted(map(canonical_sha256, a)) == sorted(map(canonical_sha256, b))


def train(key, data, inputs, refs, *, seed, epochs, messages=True):
    """Only development cases create features, labels, vocabulary or weights."""
    torch.set_num_threads(1)
    torch.use_deterministic_algorithms(True)
    torch.manual_seed(seed)
    ids = [r['id'] for r in data['rows'] if r['split'] == 'development']
    if not ids or not 1 <= epochs <= 100:
        raise ValueError('invalid training scope')
    start = time.perf_counter()
    vocab, labels = {}, []
    if key == 'E07':
        labels = sorted({refs[i][0] for i in ids})
        model = GraphNet(len(labels), messages)
        x = graph_tensor([inputs[i] for i in ids])
        y = torch.tensor([labels.index(refs[i][0]) for i in ids])
        logits = lambda: model(x)
        architecture = 'directed-message-passing-gnn' if messages else 'gnn-zero-message-ablation'
    else:
        if key in RANK:
            examples, targets = [], []
            for i in ids:
                for group in groups(key, inputs[i]):
                    hits = [j for j, (candidate, _) in enumerate(group) if candidate in refs[i]]
                    if len(hits) == 1:
                        examples.append([features for _, features in group])
                        targets.append(hits[0])
            width = len(examples[0])
            if any(len(row) != width for row in examples):
                raise ValueError('variable candidate width unsupported')
            rows = [f for row in examples for f in row]
            y = torch.tensor(targets)
        else:
            rows = [core.features(key, inputs[i]) for i in ids]
            targets = [('pending' if refs[i] else 'not_pending') if key == 'E04' else refs[i][0] for i in ids]
            labels = sorted(set(targets))
            y = torch.tensor([labels.index(t) for t in targets])
        vocab = {f: i + 2 for i, f in enumerate(sorted({f for row in rows for f in row}))}
        size = len(vocab) + 2
        sequence = key in SEQUENCE

        def encode(values):
            if sequence:
                seqs = [torch.tensor([vocab.get(f, 1) for f in row] or [1]) for row in values]
                return nn.utils.rnn.pad_sequence(seqs, batch_first=True)
            out = torch.zeros((len(values), size))
            for i, row in enumerate(values):
                for f in row:
                    out[i, vocab.get(f, 1)] += 1
            return out

        x = encode(rows)
        model = FeatureNet(size, 1 if key in RANK else len(labels), sequence)
        logits = (lambda: model(x).reshape(-1, width)) if key in RANK else (lambda: model(x))
        architecture = 'listwise-layout-pair-mlp' if key == 'E02' else 'listwise-candidate-mlp' if key == 'E13' else 'feature-token-gru' if sequence else 'structured-feature-mlp'
    opt = torch.optim.Adam(model.parameters(), lr=0.02)
    for _ in range(epochs):
        opt.zero_grad()
        loss = nn.functional.cross_entropy(logits(), y)
        loss.backward()
        opt.step()
    model.eval()
    weights = {k: v.detach().tolist() for k, v in model.state_dict().items()}
    meta = dict(id=f'{key}-{architecture}', architecture=architecture, licence='MIT', training_split='development',
                training_cases=len(ids), training_ids_sha256=canonical_sha256(ids), weights_sha256=canonical_sha256(dict(weights=weights, vocab=vocab, labels=labels)),
                parameters=sum(p.numel() for p in model.parameters()), epochs=epochs, training_seconds=time.perf_counter()-start, torch=torch.__version__)

    @torch.inference_mode()
    def predict(inp):
        if key in RANK:
            chosen, confidence = [], []
            for group in groups(key, inp):
                if group:
                    probability = model(encode([f for _, f in group])).flatten().softmax(0)
                    j = int(probability.argmax())
                    chosen.append(group[j][0])
                    confidence.append(float(probability[j]))
            return chosen, min(confidence, default=0.0)
        values = model(graph_tensor([inp])) if key == 'E07' else model(encode([core.features(key, inp)]))
        probability = values[0].softmax(0)
        j = int(probability.argmax())
        label = labels[j]
        if key == 'E04':
            match = core.workflow.TUPLE.search(inp)
            prediction = [list(match.groups())] if label == 'pending' and match else [] if label == 'not_pending' else None
        else:
            prediction = [label]
        return prediction, float(probability[j])

    return predict, meta


def guard(key, inp, pred, rule):
    """Hard evidence/capability boundaries; not a clinical authorisation system."""
    if pred is None:
        return None
    if key == 'E04' and ((rule is None and not pred) or (rule == [] and pred)):
        return None
    if key == 'E11' and pred == ['supported'] and rule != pred:
        return None
    if key == 'E13' and not all(any(c['id'] == i and c['approved'] and c['site'] == inp['site'] and c['population'] == inp['population'] for c in inp['candidates']) for i in pred):
        return None
    if key == 'E17' and any(i != 'escalate' and i not in inp['allowed'] for i in pred):
        return None
    if key == 'E20' and rule == ['insufficient'] and pred != rule:
        return None
    if key == 'E22' and ((pred in (['completed'], ['late']) and pred != rule) or (rule == ['unverifiable'] and pred != rule)):
        return None
    return pred


def calibrate(examples):
    """Exploratory threshold: >=4 retained calibration proposals, zero observed errors."""
    for threshold in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
        kept = [correct for confidence, correct in examples if confidence >= threshold]
        if len(kept) >= 4 and all(kept):
            return threshold
    return None


def unresolved(key, rule):
    return rule is None or (key == 'E17' and rule == ['escalate']) or (key == 'E22' and rule == ['unverifiable'])


def run(frozen, revision, *, epochs=60, draws=200):
    if set(frozen) != set(core.TASKS):
        raise ValueError('incomplete core suite')
    for data, exp, inputs, refs in frozen.values():
        validate_experiment(exp, data)
        if canonical_sha256(inputs) != data['sha256'] or canonical_sha256(refs) != data['reference']['sha256']:
            raise ValueError('frozen input/reference mismatch')
    rules = {'E02': lambda p: sorted(map(list, core.layout.spatial(p)), key=canonical_sha256),
             'E04': core.workflow.extract_context, 'E07': core.reach, 'E11': core.credential, 'E13': core.rank_rule,
             'E17': lambda inp: core.route_rule(inp) or ['escalate'], 'E20': core.evidence, 'E22': core.workflow.verify_steps}
    out = {}
    for key, (data, base_exp, inputs, refs) in frozen.items():
        rule = rules[key]
        classical, classic_predict = core.fit_predictor(key, data, inputs, refs)
        predict, meta = train(key, data, inputs, refs, seed=base_exp['seed'], epochs=epochs)
        meta['revision'] = revision
        calibration = []
        for row in data['rows']:
            if row['split'] == 'calibration':
                i = row['id']
                inp, r = inputs[i], rule(inputs[i])
                p, confidence = predict(inp)
                p = guard(key, inp, p, r)
                if unresolved(key, r) and p is not None and not _same(p, r):
                    calibration.append((confidence, _same(p, refs[i])))
        threshold = calibrate(calibration)

        def guarded(inp):
            return guard(key, inp, predict(inp)[0], rule(inp))

        def fallback(inp):
            r = rule(inp)
            if not unresolved(key, r) or threshold is None:
                return r
            p, c = predict(inp)
            p = guard(key, inp, p, r)
            return p if p is not None and c >= threshold else r

        def agreement(inp):
            r = rule(inp)
            return r if _same(r, guarded(inp)) else None

        predictors = dict(rules=rule, classical=classic_predict, neural=lambda inp: predict(inp)[0], guarded=guarded, fallback=fallback, agreement=agreement)
        roles = ['deterministic', 'classical', 'specialist', 'hybrid', 'hybrid', 'hybrid']
        models = {a: meta for a in ('neural', 'guarded', 'fallback', 'agreement')}
        models['classical'] = dict(id='laplace-nb', revision=revision, licence='MIT', weights_sha256=canonical_sha256(classical), training_split='development')
        if key == 'E07':
            no_messages, ablation = train(key, data, inputs, refs, seed=base_exp['seed'], epochs=epochs, messages=False)
            ablation['revision'] = revision
            predictors['no_messages'] = lambda inp: no_messages(inp)[0]
            models['no_messages'] = ablation
            roles.append('specialist')
        exp = copy.deepcopy(base_exp)
        exp['experiment_id'] += '-neural-followup'
        exp['arms'] = [dict(id=a, role=role) for a, role in zip(predictors, roles)]
        exp['neural_design'] = dict(epochs=epochs, draws=draws, calibration='zero errors among >=4 retained calibration proposals')
        result = run_experiment(exp, data, inputs, refs, predictors=predictors, models=models, source_commit=revision)
        raw = result['predictions']
        result['experiment'] = exp
        result['calibration'] = dict(threshold=threshold, eligible=len(calibration))
        result['contrasts'] = {f'{a}_vs_{b}': paired_f1_interval(raw[b], raw[a], grouping_key='family', seed=exp['seed'], draws=draws) for a,b in [('neural','rules'),('neural','classical'),('guarded','neural'),('fallback','rules'),('agreement','rules')]+([('neural','no_messages')] if key=='E07' else []) if a in raw and b in raw}
        out[key] = result
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=60)
    args = parser.parse_args()
    result = run(json.loads(args.freeze.read_text()), args.revision, epochs=args.epochs)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')


if __name__ == '__main__':
    main()
