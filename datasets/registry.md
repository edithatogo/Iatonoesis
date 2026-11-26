# Candidate data register — not yet qualified

Public accessibility does not equal redistribution rights or ethical exemption. All entries are candidates, no bytes downloaded or checksums verified. T14/#15 owns qualification before ingestion. Record authoritative version, retrieval date, license/terms, data grain, schema, SHA-256, source limitations and split method. Do not commit large/raw data or credentialed sources.

| Source | Locator | Intended tasks | Qualification limitation |
|---|---|---|---|
| PhysioNet Sepsis Challenge 2019 | https://physionet.org/content/challenge-2019/1.0.0/ | R09 R11 R20 | Verify cohort/site IDs, permissions, missingness, no causal claims |
| 4TU Sepsis Cases | https://doi.org/10.4121/uuid:915d2bfb-7e84-49ad-a286-dc35f063a460 | R13 R18 R21 | Event logs do not identify counterfactual rescue outcomes |
| 4TU Hospital Billing | https://research.tue.nl/en/datasets/hospital-billing-event-log/ | R13 R17 | Administrative events not clinical truth |
| Synthea | https://github.com/synthetichealth/synthea | R09 R19 R21 | Pin generator/revision; synthetic realism is limited |
| AIHW MyHospitals API | https://www.aihw.gov.au/hospitals/other-resources/myhospitals-api | R12 R20 | Facility attributes not real-time availability |
| CMS Provider of Services | https://data.cms.gov/provider-characteristics/hospitals-and-other-facilities | R12 R20 | US capability proxies; qualify version and rural definition |
| NHS UEC situation reports | https://www.england.nhs.uk/statistics/statistical-work-areas/uec-sitrep/ | R10 | Aggregate passive forecasting; intervention effects not identified |
| CDC FluSight | https://github.com/cdcepi/FluSight-forecast-hub | R15 R20 | Verify vintage availability; truth not underlying incidence |
| HL7 CQL | https://github.com/HL7/cql | R17 R19 | Verify code/examples license and executable oracle |
| CQL execution | https://github.com/cqframework/cql-execution | R19 | Pin version; independent reference logic |
| ClinicalTrials.gov | https://clinicaltrials.gov/data-api/api | R14 R22 | Observational trial metadata not experimental counterfactuals |
| GEO | https://www.ncbi.nlm.nih.gov/geo/ | R14 R22 | Check individual study terms, overlap, biological independence |
| OpenAlex | https://openalex.org/ | R03 R07 R22 | Metadata not evidence quality or causal truth |
| WILDS Camelyon17 | https://wilds.stanford.edu/ | R20 | Larger compute/data; defer until lightweight benchmark |
| HSSIB | https://www.hssib.org.uk/ | R18 | Public findings not causal oracle; qualify rights and avoid personal attribution |
| OHO reports | https://www.oho.qld.gov.au/ | R18 | Same restrictions; no redistribution assumed |
| MIMIC-IV demo | https://physionet.org/content/mimic-iv-demo/2.2/ | integration smoke | Small demo only, no free-text notes; full MIMIC requires credentialing and is out of scope |
| Synthetic executable rules, rosters, event logs and causal simulator | repository-generated | R10 R12–R19 R21 | Define generator, seed, oracle, equivalence checks and held-out families |

For original eight tasks use rights-cleared synthetic document/graph/decision/evidence/verification fixtures first; identify independent public task datasets in T01–T08 and qualify through T14. No dataset accepted by listing alone.
