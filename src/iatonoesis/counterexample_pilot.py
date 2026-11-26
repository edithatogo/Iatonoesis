"""T18.001 exploratory synthetic rule mutation pilot; no clinical logic or data."""
import argparse
import itertools
import json
import random
from pathlib import Path

DOMAIN = tuple(itertools.product(range(5), range(5), (0, 1), (0, 1)))
FAMILIES = ('and', 'or', 'conditional', 'majority', 'nand', 'gated', 'xor', 'two_paths')
SPLIT = {'development': FAMILIES[:3], 'calibration': FAMILIES[3:4], 'test': FAMILIES[4:]}
MUTATIONS = ('x_gt', 'x_lt', 'x_true', 'x_false', 'y_gt', 'y_lt', 'y_true', 'y_false',
             'flip_c', 'c_true', 'c_false', 'flip_d', 'd_true', 'd_false')
TRUTH = {
    'and': {3, 7, 11, 15},
    'or': {1, 2, 3, 5, 6, 7, 9, 10, 11, 13, 14, 15},
    'conditional': {2, 3, 5, 7, 10, 11, 13, 15},
    'majority': {3, 5, 6, 7, 11, 13, 14, 15},
    'nand': {0, 1, 2, 4, 5, 6, 8, 9, 10, 12, 13, 14},
    'gated': {5, 6, 7},
    'xor': {5, 6, 9, 10, 13, 14},
    'two_paths': {5, 7, 10, 11, 13, 14, 15},
}


def evaluate(family, t, u, case, mutation=None):
    """Implementation under test, expressed as Boolean rules."""
    x, y, c, d = case
    a, b = x >= t, y >= u
    if mutation == 'x_gt': a = x > t
    if mutation == 'x_lt': a = x < t
    if mutation == 'x_true': a = True
    if mutation == 'x_false': a = False
    if mutation == 'y_gt': b = y > u
    if mutation == 'y_lt': b = y < u
    if mutation == 'y_true': b = True
    if mutation == 'y_false': b = False
    if mutation == 'flip_c': c = not c
    if mutation == 'c_true': c = True
    if mutation == 'c_false': c = False
    if mutation == 'flip_d': d = not d
    if mutation == 'd_true': d = True
    if mutation == 'd_false': d = False
    return bool({
        'and': a and b, 'or': a or b, 'conditional': a if c else b,
        'majority': sum((a, b, c)) >= 2, 'nand': not (a and b),
        'gated': (a or b) and c and not d, 'xor': (a != b) and (c or d),
        'two_paths': (a and c) or (b and d),
    }[family])


def oracle(family, t, u, case, mutation=None):
    """Separately expressed finite truth table and bit transformations."""
    x, y, c, d = case
    bits = int(x >= t) | (int(y >= u) << 1) | (c << 2) | (d << 3)
    if mutation is not None:
        field, action = mutation.split('_') if mutation != 'flip_c' and mutation != 'flip_d' else (mutation[-1], 'flip')
        pos = 'xycd'.index(field)
        old = (bits >> pos) & 1
        value = {'true': 1, 'false': 0, 'flip': 1 - old,
                 'gt': int((x - t if field == 'x' else y - u) >= 1),
                 'lt': int((x - t if field == 'x' else y - u) <= -1)}[action]
        bits = (bits & ~(1 << pos)) | (value << pos)
    return bits in TRUTH[family]


def defects(family, t, u):
    """Exclude equivalents to original and collapse identical kill signatures."""
    original = [oracle(family, t, u, c) for c in DOMAIN]
    signatures = {}
    seen = set()
    for mutation in MUTATIONS:
        sig = tuple(i for i, c in enumerate(DOMAIN)
                    if oracle(family, t, u, c, mutation) != original[i])
        if sig and sig not in seen:
            signatures[mutation] = sig
            seen.add(sig)
    return signatures


def features(family, t, u, case):
    x, y, c, d = case
    return (1, int(x >= t), int(y >= u), c, d, int(x == t), int(y == u),
            abs(x - t) / 4, abs(y - u) / 4, int(evaluate(family, t, u, case)))


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def fit(families=SPLIT['development']):
    """Train a small linear regression on dev-only fraction of distinct defects killed."""
    if not families or not set(families) <= set(SPLIT['development']):
        raise ValueError('training restricted to development families')
    rows = []
    for family, t, u in itertools.product(families, (1, 2, 3), (1, 2, 3)):
        sigs = [set(s) for s in defects(family, t, u).values()]
        rows.extend((features(family, t, u, c), sum(i in s for s in sigs) / len(sigs))
                    for i, c in enumerate(DOMAIN))
    w = [0.0] * len(rows[0][0])
    for _ in range(100):
        gradient = [0.0] * len(w)
        for fs, target in rows:
            err = dot(w, fs) - target
            for j, f in enumerate(fs):
                gradient[j] += err * f
        w = [a - 0.15 * g / len(rows) for a, g in zip(w, gradient)]
    return w


def stratified_rank(score, budget):
    """Same flag-stratified ranking policy for deterministic and learned scores."""
    buckets = [sorted((i for i, case in enumerate(DOMAIN) if case[2:] == flags),
                      key=lambda i: (-score(DOMAIN[i]), i))
               for flags in itertools.product((0, 1), repeat=2)]
    return [i for group in zip(*buckets) for i in group][:budget]


def run():
    seed, budget, repeats = 1107, 8, 20
    weights = fit()
    rules = []
    for j, (family, t, u) in enumerate(itertools.product(SPLIT['test'], (1, 2, 3), (1, 2, 3))):
        selections = [('boundary', stratified_rank(lambda c: -min(abs(c[0] - t), abs(c[1] - u))
                                                     - 0.01 * (abs(c[0] - t) + abs(c[1] - u)), budget)),
                      ('learned', stratified_rank(lambda c: dot(weights, features(family, t, u, c)), budget))]
        selections += [('random', random.Random(seed + j * repeats + k).sample(range(len(DOMAIN)), budget))
                       for k in range(repeats)]
        # No test mutant outputs available to candidate selectors above.
        truth = defects(family, t, u)
        arms = []
        for arm, indices in selections:
            killed = [m for m in truth if any(evaluate(family, t, u, DOMAIN[i], m) !=
                                             evaluate(family, t, u, DOMAIN[i]) for i in indices)]
            if set(killed) != {m for m, sig in truth.items() if set(indices) & set(sig)}:
                raise ValueError('oracle disagreement')
            arms.append({'arm': arm, 'indices': indices, 'killed': killed})
        rules.append({'family': family, 't': t, 'u': u, 'denominator': len(truth), 'arms': arms})
    return {'schema_version': '0.1.0', 'task': 'T18.001', 'claim_boundary': 'synthetic_only',
            'seed': seed, 'budget': budget, 'random_repeats': repeats,
            'split': {k: list(v) for k, v in SPLIT.items()}, 'weights': weights, 'rules': rules}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(), sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
