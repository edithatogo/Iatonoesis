"""Exploratory T18.001 follow-up on new toy rule and mutation families."""
import argparse
import itertools
import json
import random
from pathlib import Path

from . import counterexample_pilot as prior

TEST_FAMILIES = ('agreement_guard', 'exact_two', 'priority', 'fallback',
                 'majority_guard', 'parity_four')
TEST_MUTATIONS = ('swap_ab', 'swap_cd', 'cross_pair', 'invert_ab',
                  'copy_ab_to_cd', 'gate_equal', 'force_cd', 'invert_equal', 'xor_bd')
TRUTH = {
    'agreement_guard': {4, 7, 8, 11},
    'exact_two': {3, 5, 6, 9, 10, 12},
    'priority': {2, 3, 4, 5, 6, 7, 9, 11},
    'fallback': {1, 5, 9, 12, 13, 14},
    'majority_guard': {7, 9, 10, 11, 13, 14, 15},
    'parity_four': {1, 2, 4, 7, 8, 11, 13, 14},
}
BUDGETS = (1, 2, 4, 8)
SEED = 2401


def evaluate(family, t, u, case, mutation=None):
    """Boolean implementation; test mutations operate on joint inputs or output."""
    x, y, c, d = case
    a, b = x >= t, y >= u
    if mutation == 'swap_ab': a, b = b, a
    if mutation == 'swap_cd': c, d = d, c
    if mutation == 'cross_pair': a, b, c, d = c, d, a, b
    if mutation == 'invert_ab': a, b = not a, not b
    if mutation == 'copy_ab_to_cd': c, d = a, b
    out = bool({
        'agreement_guard': (a == b) and (c != d),
        'exact_two': sum((a, b, c, d)) == 2,
        'priority': (a and not c) if d else (b or c),
        'fallback': (a and not b) or (not a and c and d),
        'majority_guard': (a and b and c) or (d and (a or b)),
        'parity_four': bool(a ^ b ^ c ^ d),
    }[family])
    if mutation == 'gate_equal': out = out and a == b
    if mutation == 'force_cd': out = out or (c and d)
    if mutation == 'invert_equal': out = out != (a == b)
    if mutation == 'xor_bd': out = out != bool(b and d)
    return bool(out)


def oracle(family, t, u, case, mutation=None):
    """Separate explicit truth sets and bitmask transformations."""
    x, y, c, d = case
    i = int(x >= t) | (int(y >= u) << 1) | (c << 2) | (d << 3)
    transforms = {
        'swap_ab': (i & 12) | ((i & 1) << 1) | ((i & 2) >> 1),
        'swap_cd': (i & 3) | ((i & 4) << 1) | ((i & 8) >> 1),
        'cross_pair': ((i & 3) << 2) | ((i & 12) >> 2),
        'invert_ab': i ^ 3,
        'copy_ab_to_cd': (i & 3) | ((i & 3) << 2),
    }
    out = transforms.get(mutation, i) in TRUTH[family]
    equal = i in {0, 3, 4, 7, 8, 11, 12, 15}
    if mutation == 'gate_equal': return out and equal
    if mutation == 'force_cd': return out or i in {12, 13, 14, 15}
    if mutation == 'invert_equal': return out != equal
    if mutation == 'xor_bd': return out != (i in {10, 11, 14, 15})
    return out


def signatures(family, t, u):
    original = [oracle(family, t, u, c) for c in prior.DOMAIN]
    distinct, seen = {}, set()
    for m in TEST_MUTATIONS:
        sig = tuple(i for i, c in enumerate(prior.DOMAIN)
                    if oracle(family, t, u, c, m) != original[i])
        if sig and sig not in seen:
            distinct[m] = sig
            seen.add(sig)
    return distinct


def masks_for(sigs):
    masks = [0] * len(prior.DOMAIN)
    for bit, signature in enumerate(sigs.values()):
        for i in signature:
            masks[i] |= 1 << bit
    return masks


def exact_ceiling(masks, budgets):
    """Omniscient attainable maximum, DP over distinct signature bitsets."""
    choices = set(masks)
    states = {0}
    out = {}
    for k in range(1, max(budgets) + 1):
        states = states | {a | b for a in states for b in choices}
        if k in budgets:
            out[k] = max(x.bit_count() for x in states)
    return out


def case_data(family, t, u):
    ev = prior.evaluate if family in prior.FAMILIES else evaluate
    rows = []
    for x, y, c, d in prior.DOMAIN:
        a, b = int(x >= t), int(y >= u)
        out = int(ev(family, t, u, (x, y, c, d)))
        base = (1, a, b, c, d, int(x == t), int(y == u), abs(x-t)/4, abs(y-u)/4, out)
        regime = (a, b, c, d, out, (x > t)-(x < t), (y > u)-(y < u))
        tags = frozenset((i, j, regime[i], regime[j])
                         for i, j in itertools.combinations(range(len(regime)), 2))
        boundary = -min(abs(x-t), abs(y-u)) - 0.01*(abs(x-t)+abs(y-u))
        rows.append((base, regime, tags, boundary))
    return rows


def context(rows, selected):
    covered = set().union(*(rows[i][2] for i in selected))
    regimes = [rows[i][1] for i in selected]
    return covered, regimes


def novelty(row, covered, regimes):
    _, regime, tags, _ = row
    new = len(tags - covered) / len(tags)
    distance = min((sum(a != b for a, b in zip(regime, r))/len(regime) for r in regimes), default=1)
    return new, distance


def state_features(row, covered, regimes, step, total, last):
    return (*row[0], *novelty(row, covered, regimes), step/8, total/16, last/16)


def training_rows():
    rows = []
    for n, (family, t, u) in enumerate(itertools.product(prior.SPLIT['development'], (1, 2, 3), (1, 2, 3))):
        data = case_data(family, t, u)
        masks = masks_for(prior.defects(family, t, u))
        for repeat in range(6):
            rng = random.Random(SEED + n*6 + repeat)
            selected, seen, last = [], 0, 0
            for step in range(8):
                covered, regimes = context(data, selected)
                remaining = [i for i in range(len(data)) if i not in selected]
                for i in rng.sample(remaining, 8):
                    fs = state_features(data[i], covered, regimes, step, seen.bit_count(), last)
                    rows.append((fs, (masks[i] & ~seen).bit_count()/16))
                chosen = rng.choice(remaining)
                last = (masks[chosen] & ~seen).bit_count()
                seen |= masks[chosen]
                selected.append(chosen)
    return rows, {'families': list(prior.SPLIT['development']), 'mutations': list(prior.MUTATIONS),
                  'seed': SEED, 'histories_per_instance': 6, 'candidate_labels_per_step': 8,
                  'rows': len(rows), 'ridge_penalty': 1}


def ridge(rows, feedback):
    """Small regularised normal equation with deterministic pivoted elimination."""
    n = len(rows[0][0]) - (0 if feedback else 2)
    a = [[float(i == j) for j in range(n)] + [0.0] for i in range(n)]
    for fs, y in rows:
        for i in range(n):
            for j in range(n):
                a[i][j] += fs[i]*fs[j]
            a[i][-1] += fs[i]*y
    for i in range(n):
        pivot = max(range(i, n), key=lambda j: abs(a[j][i]))
        a[i], a[pivot] = a[pivot], a[i]
        v = a[i][i]
        a[i] = [x/v for x in a[i]]
        for j in range(n):
            if i != j:
                v = a[j][i]
                a[j] = [x-v*y for x, y in zip(a[j], a[i])]
    return [r[-1] for r in a]


def select(arm, family, t, u, budget, weights, feedback, seed=SEED):
    """Only feedback-aware arms query outcomes, and only after selection."""
    if not 1 <= budget <= len(prior.DOMAIN):
        raise ValueError('invalid budget')
    rng = random.Random(seed)
    if arm == 'random':
        return rng.sample(range(len(prior.DOMAIN)), budget)
    if arm == 'stratified_random':
        buckets = [[i for i, c in enumerate(prior.DOMAIN) if c[2:] == flags]
                   for flags in itertools.product((0, 1), repeat=2)]
        for bucket in buckets: rng.shuffle(bucket)
        return [i for group in zip(*buckets) for i in group][:budget]
    data = case_data(family, t, u)
    if arm == 'boundary':
        return prior.stratified_rank(lambda c: data[prior.DOMAIN.index(c)][3], budget)
    if arm == 'old_linear':
        return prior.stratified_rank(lambda c: prior.dot(weights, data[prior.DOMAIN.index(c)][0]), budget)
    if arm not in {'pairwise', 'adaptive_coverage', 'learned_no_feedback', 'learned_feedback'}:
        raise ValueError('unknown arm')
    selected, total, last = [], 0, 0
    for step in range(budget):
        covered, regimes = context(data, selected)
        def key(i):
            row = data[i]
            new, distance = novelty(row, covered, regimes)
            if arm == 'pairwise': return (new, distance, row[3], -i)
            if arm == 'adaptive_coverage':
                return (new, row[3], distance, -i) if last else (new, distance, row[3], -i)
            fs = state_features(row, covered, regimes, step, total, last)
            if arm == 'learned_no_feedback': fs = fs[:-2]
            return (prior.dot(weights, fs), new, distance, -i)
        chosen = max((i for i in range(len(data)) if i not in selected), key=key)
        selected.append(chosen)
        if arm in {'adaptive_coverage', 'learned_feedback'}:
            last, total = feedback(chosen)
    return selected


def run():
    train, provenance = training_rows()
    weights = {'old_linear': prior.fit(), 'learned_no_feedback': ridge(train, False),
               'learned_feedback': ridge(train, True)}
    rules = []
    for n, (family, t, u) in enumerate(itertools.product(TEST_FAMILIES, (1, 2, 3), (1, 2, 3))):
        truth = signatures(family, t, u)
        masks = masks_for(truth)
        if not truth:
            raise ValueError('no non-equivalent signatures')
        arms = []
        for arm, repeat in [('random', i) for i in range(20)] + [('stratified_random', i) for i in range(20)] + [(a, 0) for a in ('boundary', 'old_linear', 'pairwise', 'adaptive_coverage', 'learned_no_feedback', 'learned_feedback')]:
            seen = 0
            def observe(i):
                nonlocal seen
                new = (masks[i] & ~seen).bit_count()
                seen |= masks[i]
                return new, seen.bit_count()
            indices = select(arm, family, t, u, 8, weights.get(arm, ()), observe, SEED + n*20 + repeat)
            killed = {str(k): [m for m in truth if any(evaluate(family, t, u, prior.DOMAIN[i], m) != evaluate(family, t, u, prior.DOMAIN[i]) for i in indices[:k])] for k in BUDGETS}
            for k in BUDGETS:
                if set(killed[str(k)]) != {m for m, s in truth.items() if set(indices[:k]) & set(s)}:
                    raise ValueError('oracle mismatch')
            arms.append({'arm': arm, 'repeat': repeat, 'indices': indices, 'killed': killed})
        rules.append({'family': family, 't': t, 'u': u, 'denominator': len(truth),
                      'oracle_ceiling': {str(k): v for k, v in exact_ceiling(masks, BUDGETS).items()}, 'arms': arms})
    return {'schema_version': '0.2.0', 'task': 'T18.001', 'claim_boundary': 'synthetic_only',
            'training': provenance, 'test_families': list(TEST_FAMILIES), 'test_mutations': list(TEST_MUTATIONS),
            'budgets': list(BUDGETS), 'original_candidate_pool': len(prior.DOMAIN), 'weights': weights, 'rules': rules}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
