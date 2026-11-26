"""Task-specific metrics; undefined ratios are null, never silently zero."""
import math


def _finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def _paired(a, b):
    if not a or len(a) != len(b) or not all(_finite(x) for x in (*a, *b)):
        raise ValueError('nonempty paired finite values required')


def continuous(targets, predictions, *, radius=None):
    _paired(targets, predictions)
    errors = [abs(y-p) for y, p in zip(targets, predictions)]
    n = len(errors)
    mse = sum(e*e for e in errors)/n
    out = dict(n=n, mae=sum(errors)/n, mse=mse, rmse=math.sqrt(mse))
    if radius is not None:
        if not _finite(radius) or radius < 0:
            raise ValueError('invalid interval radius')
        covered = sum(e <= radius for e in errors)
        out.update(interval_n=n, interval_covered=covered, interval_coverage=covered/n,
                   interval_width=2*radius, radius=radius)
    return out


def conformal_radius(errors, *, coverage=.9):
    if not errors or not 0 < coverage < 1 or not all(_finite(x) and x >= 0 for x in errors):
        raise ValueError('invalid calibration residuals or coverage')
    k = math.ceil((len(errors)+1)*coverage)
    if k > len(errors):
        raise ValueError('insufficient calibration for finite interval')
    return sorted(errors)[k-1]


def calibration(labels, probabilities, *, bins=10):
    _paired(labels, probabilities)
    if (type(bins) is not int or bins < 1 or not all(y in (0, 1) for y in labels)
            or not all(0 <= p <= 1 for p in probabilities)):
        raise ValueError('invalid binary calibration input')
    groups = [[] for _ in range(bins)]
    for y, p in zip(labels, probabilities):
        groups[min(bins-1, int(p*bins))].append((y, p))
    rows = []
    for i, group in enumerate(groups):
        n = len(group)
        rows.append(dict(lower=i/bins, upper=(i+1)/bins, n=n,
                         observed=sum(y for y, _ in group)/n if n else None,
                         predicted=sum(p for _, p in group)/n if n else None))
    n = len(labels)
    return dict(n=n, brier=sum((y-p)**2 for y, p in zip(labels, probabilities))/n,
                ece=sum(b['n']*abs(b['observed']-b['predicted']) for b in rows if b['n'])/n,
                bins=rows)


def ranking(order, qrels, k):
    if (type(k) is not int or not 1 <= k <= len(order) or len(set(order)) != len(order)
            or not all(type(v) is int and v >= 0 for v in qrels.values())):
        raise ValueError('invalid ranking input')
    if set(order) != set(qrels):
        raise ValueError('complete judged fixed pool required')
    top = [qrels[i] for i in order[:k]]
    total = sum(v > 0 for v in qrels.values())
    found = sum(v > 0 for v in top)
    def dcg(scores):
        return sum((2**v-1)/math.log2(i+2) for i, v in enumerate(scores))
    ideal = dcg(sorted(qrels.values(), reverse=True)[:k])
    return dict(k=k, pool=len(order), positives=total, retrieved_positives=found,
                precision=found/k, recall=found/total if total else None,
                ndcg=dcg(top)/ideal if ideal else None)


def mutation_coverage(signatures, selected, *, pool_size, budget):
    def valid(i):
        return type(i) is int and 0 <= i < pool_size
    if (type(pool_size) is not int or pool_size < 1 or type(budget) is not int
            or not 1 <= budget <= pool_size or len(selected) > budget
            or not all(valid(i) for i in selected) or len(set(selected)) != len(selected)):
        raise ValueError('invalid selection or budget')
    unique = set()
    for sig in signatures.values():
        if not all(valid(i) for i in sig):
            raise ValueError('invalid reference signature')
        if sig:
            unique.add(frozenset(sig))
    found = sum(bool(s.intersection(selected)) for s in unique)
    return dict(pool_size=pool_size, budget=budget, selected=len(selected),
                distinct_defects=len(unique), detected=found,
                coverage=found/len(unique) if unique else None)


def paired_mean_difference(baseline_losses, challenger_losses, *, seed, draws=1000):
    """Descriptive paired subject bootstrap; caller must ensure independent units."""
    import random
    _paired(baseline_losses, challenger_losses)
    n = len(baseline_losses)
    if n < 2 or type(draws) is not int or not 1 <= draws <= 100000:
        raise ValueError('invalid paired bootstrap size')
    differences = [b-a for a,b in zip(baseline_losses, challenger_losses)]
    rng = random.Random(seed)
    values = sorted(sum(rng.choice(differences) for _ in range(n))/n for _ in range(draws))
    return dict(n=n, draws=draws, seed=seed, difference=sum(differences)/n,
                lower=values[int(.025*(draws-1))], upper=values[math.ceil(.975*(draws-1))])
