# V3 implementation and reproduction guide

3 November 2026 · Experimental research software · Frozen 0.6 converter preserved

## What is implemented

The V3 research package is `research/ifc_citygml_v3`. Its executable entry point is `scripts/research_v3.py`. The original installed converter and V2 research files remain separate and unchanged. V3 is not silently installed into the preserved wheel.

| Component | Implementation and practical scope |
| --- | --- |
| Named conversion policy | Strict metric budgets, explicit repair permission and source interaction limits |
| Connection evidence | Logical-only links separated from supported plane geometry; local connection planes transformed to engineering metres |
| Constrained repair | Projects opposed, overlapping support faces onto consistent declared planes, with cumulative displacement limits and an operation ledger |
| Conservative interaction index | Sweep-based AABB candidate pairs; pruning is tied to twice the maximum per-element influence distance |
| Conversion decisions | Unquantised and conditioned candidates, with/without justified plane edits; accepted, review, rejected and execution outcomes retained |
| CityGML serialization | Seventeen significant decimal digits and a checked roundtrip to the same binary mesh coordinates |
| Source correspondence | Contact/component checks, single-source boundary sampling, protected separations and explicit unresolved cases |
| Additional diagnostics | Oriented shell/Euler indicators, signed cavity winding and post-evaluation contact-interface localisation; not formal certificates |
| Query-specific generalisation | Identity, building bounds and Manifold simplification candidates; measured error, volume, topology and protected-probe gates; Pareto filtering |
| Incremental conversion | Conservative building-level Boolean reuse; fingerprints include geometry, source metadata, policy, relationships and coordinate metadata; full rebuild verification enabled by default |
| Evidence queries | GUID-based lineage inspection and an experimental JSON-LD export with a declared custom vocabulary |
| Independent-review workflow | Empty, artifact-scoped templates; browser review form; hash-checked reference import and reviewer-agreement calculation |
| Urban sensitivity | Same hazard and matched feature identities across representations and declared horizontal scenarios; no invented probability or water depth |
| IFC4X3 follow-up adapter | Explicit opt-in building subset with ordinary local placements; map metadata retained without geographic application; no general infrastructure qualification |
| Resource guard | Refuses unqualified source-mesh complexity without truncating triangles or accepting partial content |
| Exact arithmetic comparator | Locally compiled CGAL rational Boolean executable, separate serialized validation and retained rational vertices; no qualified per-face lineage |

## Implemented experiments and observed limits

Two 80-input development runs and a 160-input fresh holdout retain 960 main attempt records across three methods. The corrected development repeats the same physical inputs with a fixed party-wall reference, so these are not 320 independent buildings. The main suites contain 240 distinct IFC input hashes. All analytical controls remain related designs. The holdout is 480 attempts and was not used to tune the evaluated conversion algorithm.

The V3 constrained method accepts 115 of the 160 holdout inputs. Of those, 111 pass all registered reference checks and four fail. Eleven require review, 33 are rejected and one encounters a measurement/execution failure. The accepted failures include three tilted designs with 3D surface-distance discrepancies and a party-wall case with a footprint-boundary discrepancy despite a small 3D distance. Post-evaluation diagnostics do not revise these frozen outcomes. They remain research limitations and prevent general release promotion.

The overall V2 comparison includes new declared-interface targets that the source-only baseline does not implement. Its aggregate failure counts cannot establish that the V3 numerical method is generally superior. Report mechanism-specific scope and coverage alongside accepted errors.

The eight original V2 accepted failures were re-audited separately. Five were induced by an analytical-reference defect: constructing a cell arrangement from already scaled floating-point coordinates introduced tiny extra cells/interfaces. Corrected references construct the unscaled arrangement first and apply scale once. Three failures persist; V3 routes those historical cases to review. All original references, outputs and reports remain preserved. These historical diagnoses are not fresh validation.

The exact comparator completes six of seven small/historical trials; one reaches its 90-second limit. Four basic gap controls meet the design checks. Two completed historical unions still differ from intended design, demonstrating why exact arithmetic on extracted doubles cannot infer intended contacts. CGAL is a comparison track, not the default attributed converter.

On the five-building revision demonstration, all five states match the full rebuild in canonical geometry, source lineage and decision. Single-building edits reuse four buildings; the unchanged revision reuses all five. Some small edits are slower because invalidation, per-building validation and cache overhead exceed the full rebuild cost. No general speedup is claimed.

For a cylinder, an admissible query representation uses 56 triangles instead of 792 under the registered 0.2 m sampled boundary and 10% volume limits, while preserving component/Euler indicators. A courtyard bounding block is rejected because it changes the topology and fills a protected void. Measured finite samples and indicators are not a certified global error bound or complete opening-preservation proof.

The fixed-hazard synthetic example measures 9 m² intersected material-union footprint versus 21 m² for its bounding block. The selected ±0.1 m scenarios do not alter either result. This is a controlled representation/sensitivity example, not a Torino building or hydraulic study.

The complete suite initially passed 175 tests. Six additional distinct targeted checks cover artifact-scoped review, resource refusal, signed cavity winding and measurement-error retention; the latest combined records cover 181 distinct passing tests. The viewer/review surface passes 16 browser checks. Test records and exact result indexes are retained under `results/v3`.

## Open data and the external reference gate

The [SUM4Re release of 30 October 2026](https://zenodo.org/records/23808860) provides five IFCs and paired-by-name HL2 point-cloud files in the acquired bounded subset. All ten files are downloaded under the publisher's CC BY 4.0 declaration and verified against its MD5 values. These extend the retained public corpus to 31 distinct IFC hashes. The target/donor pair and other related sites are not automatically independent projects.

Five filename pairings and raw scan metadata were audited. Registration, physical reference independence and semantic truth remain unestablished. No scan accuracy or semantic score is fabricated. The initial strict conversion trial has three timeouts and two unsupported outcomes. The separate IFC4X3 development follow-up exposes a memory-allocation failure and further limitations. The resource-bounded follow-up rejects three inputs and times out on two. None qualifies a strict material union on these data.

The bounded adapter limits each selected source element to 20,000 triangles and one million vertex×face halfspace entries. Oversized geometry is explicitly failed; no geometry is truncated. SDK tessellation itself and other processing can still reach the process timeout. This resource policy is a conservative eligibility restriction, not evidence of scalable conversion on large buildings.

No verified Torino building IFC with independent survey controls has been acquired. Official Torino context remains available from the earlier project. Independent reviewers, a geographically suitable local reference pairing and any hydraulic observations remain external scientific dependencies. Their import/evaluation software is implemented; the evidence itself cannot be generated by declaring a CSV independent.

## Environment and native build

Use the project virtual environment. The original pinned dependencies remain in `requirements.lock.txt`. Optional V3 packages are pinned in `research/requirements_v3_optional.txt`: psutil, laspy and lazrs. The native track uses CGAL 6.2.1, Boost 1.87.0, the locally available MSVC toolchain and task-local Microsoft SDK headers/libraries. Source archives, URLs, checksums, build logs and executable hashes are retained under `tools/v3_native`.

CGAL PMP licence terms apply to the comparison dependency; the native binary is not added to the preserved converter distribution. Microsoft SDK packages are local compilation dependencies and are not redistributed as project software. Public IFC/scan attribution is retained in the raw source manifest.

```powershell
.venv\Scripts\python.exe scripts/acquire_v3_dependencies.py
.venv\Scripts\python.exe scripts/acquire_v3_sdk.py
.venv\Scripts\python.exe scripts/build_v3_native.py --exact-log
```

The exact comparator uses `Simple_cartesian<Quotient<MP_Float>>`. Its input doubles are represented exactly inside that arithmetic. OFF/GML double serialization and geometric validation are separate stages. The initial quotient-text logs use CGAL's approximate stream formatting and are not exact records. A separate corrected executable emits exact limb expressions; two replayed controls reconstruct the rational coordinates and preserve the original OFF bytes. An additional intersecting-box test reconstructs ten non-dyadic coordinates, with approximately 2.84e-14 m maximum floating export error. See `results/v3/exact_logging_check` and `results/v3/exact_intersection_check`. Exactness does not extend backwards through the IFC tessellator or establish author intent.

## Using the research CLI

Run from the project root. All output examples below use new paths. Existing outputs are protected from replacement.

```powershell
.venv\Scripts\python.exe scripts/research_v3.py --help
.venv\Scripts\python.exe scripts/research_v3.py convert INPUT.ifc --output results/my_conversion
.venv\Scripts\python.exe scripts/research_v3.py convert IFC43_BUILDING.ifc --experimental-ifc43 --output results/my_ifc43_trial
.venv\Scripts\python.exe scripts/research_v3.py generalise results/my_conversion/report.json --output results/my_generalisation
.venv\Scripts\python.exe scripts/research_v3.py update REVISION.ifc --cache results/my_cache.json --output results/my_revision
.venv\Scripts\python.exe scripts/research_v3.py trace results/my_conversion/report.json --guid SOURCE_GUID --output results/my_trace.json
.venv\Scripts\python.exe scripts/research_v3.py topology OUTPUT.gml --output results/my_topology.json
```

The incremental path falls back to complete rebuilding for cross-building connection cases and other unqualified combinations. It reports building-level granularity explicitly. The `--skip-rebuild-verification` option leaves the equivalence check unverified and should not be used for a correctness claim.

```powershell
.venv\Scripts\python.exe scripts/research_v3.py review-template REPORT.json --output results/review_A.csv
.venv\Scripts\python.exe scripts/research_v3.py evaluate-review REPORT.json results/review_A.csv --output results/semantic_score.json
.venv\Scripts\python.exe scripts/research_v3.py review-agreement results/review_A.csv results/review_B.csv --output results/reviewer_agreement.json
```

Reference rows require label, reviewer identity, evidence URI and an explicit independence declaration. V3 scoring additionally requires matching input and output SHA-256 values. Blank/unscoped records are not scored; records from a different output are rejected. The browser export includes only the currently selected artifact. Source hints are predictions, not reference truth. The supplied demonstration templates remain blank.

For scenario analysis, `profiles.json` maps profile names to GeoJSON feature collections with the same source feature IDs. Both profiles and hazard need a declared shared projected metre frame; any embedded CRS must agree. Use only supplied coordinate evidence or explicitly constructed synthetic scenarios.

```powershell
.venv\Scripts\python.exe scripts/research_v3.py sensitivity profiles.json hazard.geojson --crs EPSG:32632 --coordinate-status synthetic_truth --offsets '[[0,0],[-0.1,0],[0.1,0]]' --provenance 'Declared sensitivity scenarios, not observed uncertainty' --output results/scenarios.json
```

Entrance and water-level interpretation must still satisfy the earlier project's vertical-reference gate. No hydraulic simulation, water-depth prediction or building damage estimate is implemented or inferred by this scenario command.

## Reproducing experiments and artifacts

Use fresh output directories; do not delete frozen outputs to force a rerun.

```powershell
.venv\Scripts\python.exe scripts/research_v3.py prepare --partition development --count 80 --output data/derived/my_dev
.venv\Scripts\python.exe scripts/research_v3.py benchmark data/derived/my_dev/manifest.json --output results/my_dev --workers 3
.venv\Scripts\python.exe scripts/compare_v3_exact.py
.venv\Scripts\python.exe -m pytest -q
```

The fixed experiment scripts protect their existing outputs, so a reproduction should use a separate checkout or explicitly revise their output-root setting. The current holdout seed and results are now inspected; repeating them does not create fresh validation. Register a new protocol and genuinely new partition for subsequent tuning. Fresh benchmarks save a code snapshot; the initial development versions were separately archived with hashes matching their original protocols. The current CLI uses `safe_benchmark.py`, a separately versioned telemetry improvement that retains GML, the conversion status and decision ledger even if reference measurement fails. The original holdout runner and results are unchanged; the inspected exception was replayed separately to recover its complete record, not to claim additional validation.

Figure and viewer build commands are `build_v3_viewer.py`, `verify_v3_viewer.py`, `build_v3_figures.py` and `build_v3_report.py`. The viewer is a local HTML file with embedded geometry and no CDN dependency. Editable SVGs and 3200×2000 PNGs accompany the PDF. Headless Chrome supplies depth-buffer renderings; the PDF is rendered to page images and inspected.

## Research positioning and unfinished qualification

Existing exact Boolean libraries and graph-based traceability are prior capabilities, not novelty claims. Relevant current work already compares translation and reinterpretation using RDF and records conversion decisions. The proposed distinguishing research question concerns evidence-constrained interface edits, explicit abstention and task/revision consistency; demonstrating novelty and external generality still needs a broader independent comparison. [Publisher source](https://www.mdpi.com/2220-9964/15/11/483), [CGAL documentation](https://doc.cgal.org/6.2/PMP_Boolean_operations/index.html), [buildingSMART connection definition](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcRelConnectsElements.htm).

The execution status records implementation separately from qualification. Complete independent annotation, as-built/local validation, globally certified boundary/void preservation and supported-release promotion remain unfinished. The frozen conversion candidate is not retuned after its holdout; additional error-localisation diagnostics are explicitly post-evaluation. A publication-ready general converter is not claimed.
