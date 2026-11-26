"""Post-hoc bundle-time sensitivity on the retained aggregate T16.001 receipt."""
import argparse
import hashlib
import json
import math
from pathlib import Path

RAW_SHA = 'c5df78bb351ea395eb112fcccddbab16b1cb95094f07863ddcd752bf8f1b2774'
MANIFEST = '5b6073d8241353b1f56e431b05c68fc544b15b9da2cb9c9ce5ac41686dc7426f'
ARMS = ('fixed', 'greedy', 'context', 'context_stop')
# Dall'Ora et al., Table 3: distinct arithmetic-mean estimands, not pooled.
SCENARIOS = (('bedside', 225, 212, 238), ('round', 301, 279, 324),
             ('round_with_interruptions', 386, 361, 410))


def incidence(n, count):
    """Sharp integer bounds on patients with any acquisition, at most 3 each."""
    if type(n) is not int or type(count) is not int or n < 1 or not 0 <= count <= 3*n:
        raise ValueError('invalid population or observation count')
    return (count+2)//3, min(n, count)


def analyze(raw):
    digest = hashlib.sha256(raw).hexdigest()
    if digest != RAW_SHA:
        raise ValueError('aggregate digest mismatch')
    data = json.loads(raw)
    if data['source_manifest_sha256'] != MANIFEST:
        raise ValueError('source manifest mismatch')
    n = data['acquisition_counts']['test']
    incidence(n, 0)
    groups = data['acquisition']['equal']
    extracted = {}
    for cap in ('0', '3'):
        group = groups[cap]
        arms = group['receipt']['arms']
        if group['costs'] != [1, 1, 1] or len(arms) != len(ARMS) or {a['id'] for a in arms} != set(ARMS):
            raise ValueError('unexpected comparison arms or budget')
        for arm in arms:
            name, m = arm['id'], arm['metrics']
            if arm['status'] != 'executed' or (m['total'], m['scored'], m['abstained']) != (n, n, 0):
                raise ValueError('paired denominator mismatch')
            mse = m['mse']
            spend = group['spend'][name]
            obs = spend['mean_observations']
            if not math.isfinite(mse) or mse < 0 or not math.isfinite(obs) or obs != spend['mean_spend']:
                raise ValueError('invalid loss or count')
            total = round(obs*n)
            if not math.isclose(obs*n, total, rel_tol=0, abs_tol=1e-7):
                raise ValueError('nonintegral observation count')
            incidence(n, total)
            if (cap == '0' and total != 0) or (cap == '3' and name != 'context_stop' and total != 3*n):
                raise ValueError('unexpected forced acquisition count')
            extracted[cap, name] = (mse, total)
    base = extracted['0', 'fixed'][0]
    full = extracted['3', 'fixed'][0]
    if any(extracted['0', a][0] != base for a in ARMS) or any(extracted['3', a][0] != full for a in ARMS[:-1]):
        raise ValueError('matched endpoint convergence failure')
    stop, count = extracted['3', 'context_stop']
    lo, hi = incidence(n, count)
    gain = base-stop
    scenarios = []
    for name, seconds, low_ci, high_ci in SCENARIOS:
        low, high = seconds*lo/n, seconds*hi/n
        scenarios.append(dict(id=name, published_mean_seconds=seconds, published_mean_ci=[low_ci, high_ci],
                              full_mean_seconds=seconds, stop_mean_seconds_bounds=[low, high],
                              stop_staff_hours_per_100_bounds=[low*100/3600, high*100/3600],
                              stop_break_even_loss_per_staff_minute_bounds=[gain*60/high, gain*60/low] if gain>0 and low>0 else None))
    return dict(scope='posthoc_counterfactual_bundle_time_sensitivity_not_clinical_cost',
                source_run=45815419126, source_artifact=15116315352, source_sha256=digest, source_manifest_sha256=MANIFEST,
                population=n, baseline_mse=base, full=dict(mse=full, delta_mse=full-base, dominated_on_point_estimates=full>=base),
                stop=dict(mse=stop, mse_reduction=gain, observations=count, bundle_count_bounds=[lo, hi]),
                scenarios=scenarios, paired_stop_vs_none=None,
                paired_stop_vs_full=groups['3']['spend']['context_stop'].get('paired_delta_vs_fixed'),
                timing_source='https://doi.org/10.1016/j.ijnurstu.2021.103921',
                context_only_geometric_means=[dict(mode='paper', seconds=215, ci=[177,262]),dict(mode='electronic', seconds=150, ci=[130,172])],
                context_source='https://pubmed.ncbi.nlm.nih.gov/28339626/',
                limitations=['one extra whole bundle whenever any masked observation is requested is a scenario, not an observed clinical action',
                             'whole vital-sign bundles may include the withheld HR target itself; this is not an actual collection workflow',
                             'no measured marginal component, record-access, local staffing or rural travel costs',
                             'bundle-incidence bounds are identification bounds at fixed published means, not confidence intervals',
                             'published mean CIs are separate; geometric means not substituted for expected total time',
                             'descriptive loss only; no paired uncertainty versus no acquisition and no clinical utility or economic adoption decision'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.write_text(json.dumps(analyze(a.source.read_bytes()),sort_keys=True,indent=2,allow_nan=False)+'\n')


if __name__ == '__main__':
    main()
