"""New synthetic policy-link families; no reuse of the seed-17 test pages."""
import random

SEED = 27183
FAMILIES = (
    ('wide_right_dev', 'development'),
    ('wide_left_cal', 'calibration'),
    ('alternating_sides', 'test'),
    ('uneven_columns', 'test'),
    ('offset_small_markers', 'test'),
    ('ambiguous_midpoint', 'test'),
    ('missing_conflicting', 'test'),
)


def generate():
    rng = random.Random(SEED)
    pages = []
    for family, split in FAMILIES:
        for n in range(8):
            ids = rng.sample(list('ABCDEF'), 6)
            numbers = rng.sample(range(10, 99), 6)
            abstract = [(r, f'{m:02}', f'EXCEPTION-{rng.getrandbits(24):06X}')
                        for r, m in zip(ids, numbers)]
            gold = sorted([r, note] for r, _, note in abstract)
            reqs, marks, notes = [], [], []
            for i, (req, marker, note) in enumerate(abstract):
                col, row = i % 2, i // 2
                x = (100, 372)[col] + rng.randint(-8, 8)
                y = 113 + row * 56 + rng.randint(-3, 3)
                if family == 'uneven_columns':
                    x = (122, 328)[col] + rng.randint(-16, 16)
                    y += 15 * col
                if family == 'ambiguous_midpoint':
                    x = (105, 209)[col]
                    y = 110 + row * 56
                side = -1 if family == 'wide_left_cal' else 1
                if family in {'alternating_sides', 'uneven_columns', 'offset_small_markers', 'missing_conflicting'}:
                    side = -1 if (i + n) % 2 else 1
                gap = rng.randint(30, 51)
                mx = x + 40 + gap if side > 0 else x - 20 - gap
                my = y + rng.randint(-2, 2)
                size = 12
                if family == 'offset_small_markers':
                    my = y - 7 if i % 2 else y + 4
                    size = 9
                if family == 'ambiguous_midpoint' and i % 2 == 0:
                    mx = x + 62
                if family == 'ambiguous_midpoint' and i % 2:
                    mx = x + 74
                reqs.append(dict(text=f'REQ-{req}', x=x, y=y, size=12))
                mark = dict(text=f'*{marker}', x=mx, y=my, size=size)
                if family == 'missing_conflicting' and i == 0:
                    mark = None
                marks.append(mark)
                notes.append(dict(text=f'*{marker}:{note}', x=68, y=450, size=11))
            if family == 'missing_conflicting':
                notes.append(dict(text=f'*{abstract[1][1]}:EXCEPTION-CONFLICT', x=68, y=450, size=11))
            rng.shuffle(notes)
            for i, note in enumerate(notes):
                note['y'] += i * 23
            tokens = reqs + [m for m in marks if m is not None]
            rng.shuffle(tokens)
            tokens += notes
            pages.append(dict(id=f'v2-{family}-{n:02}', family=family, split=split,
                              gold=gold, tokens=tokens))
    return pages
