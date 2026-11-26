"""Audit the complete upstream EQUATOR metadata census, not checklist text or model accuracy."""
import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

STATUSES = {'lookup_incomplete', 'metadata_only', 'missing_identifier', 'oa_xml_candidate',
            'identity_conflict', 'unresolved'}
STRATA = ('study_types', 'clinical_areas', 'report_sections')


def indexed(rows):
    result = {}
    for row in rows:
        key = row['id']
        if not isinstance(key, str) or not key or key in result:
            raise ValueError('missing or duplicate directory identity')
        result[key] = row
    return result


def census(catalogue, survey):
    """Conserve directory identities and keep overlapping source-defined strata distinct."""
    revision = catalogue['source_revision']
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or survey['source_revision'] != revision:
        raise ValueError('source revision mismatch')
    cat, obs = indexed(catalogue['guidelines']), indexed(survey['records'])
    if (not cat or cat.keys() != obs.keys() or len(cat) != catalogue['published_count']
            or len(cat) != survey['summary']['published_count']):
        raise ValueError('incomplete census join')
    acquisitions = survey['priority_articles'] + survey['bulk_articles']
    if survey['summary']['canonical_packs_promoted'] != 0 or any(
            row['canonical_packs_promoted'] != 0 for row in acquisitions):
        raise ValueError('unexpected promotion in discovery receipt')
    status = Counter()
    strata = {field: defaultdict(Counter) for field in STRATA}
    for key, row in cat.items():
        observed = obs[key]
        if not re.fullmatch(r'[0-9a-f]{40}', row['source_blob_sha']) or row['source_blob_sha'] != observed['source_blob_sha']:
            raise ValueError('source fingerprint mismatch')
        state = observed['status']
        if state not in STATUSES:
            raise ValueError('unknown discovery status')
        status[state] += 1
        for field in STRATA:
            groups = row.get(field) or ['(unspecified)']
            if not isinstance(groups, list) or any(not isinstance(g, str) or not g.strip() for g in groups):
                raise ValueError('invalid stratum')
            for group in set(groups):
                strata[field][group][state] += 1
    if 'status_counts' in survey['summary'] and dict(status) != survey['summary']['status_counts']:
        raise ValueError('survey summary does not reconcile')
    def summary(counts):
        n = sum(counts.values())
        return dict(population=n, status_counts=dict(sorted(counts.items())),
                    oa_candidate_fraction=counts['oa_xml_candidate'] / n)
    return dict(schema_version='0.1.0', source_revision=revision, **summary(status),
                metadata_review_count=sum(row['metadata_status']=='needs_review' for row in cat.values()),
                priority_acquisition_status_counts=dict(sorted(Counter(row['status'] for row in survey['priority_articles']).items())),
                bulk_acquisition_status_counts=dict(sorted(Counter(row['status'] for row in survey['bulk_articles']).items())),
                strata={field: {group: summary(counts) for group, counts in sorted(groups.items())}
                        for field, groups in strata.items()},
                membership='overlapping categories; do not sum across strata',
                claim_boundary='acquisition_coverage_not_model_performance',
                canonical_packs_promoted=0, model_runs=0)


def from_zip(path, expected_sha256):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError('artifact digest mismatch')
    with zipfile.ZipFile(path) as archive:
        names = ('equator-catalogue.json', 'equator-article-survey.json')
        raw = [archive.read(name) for name in names]
    result = census(*(json.loads(data) for data in raw))
    result['input_sha256'] = dict(zip(names, (hashlib.sha256(data).hexdigest() for data in raw)))
    result['archive_sha256'] = digest
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(from_zip(args.archive, args.sha256), sort_keys=True, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
