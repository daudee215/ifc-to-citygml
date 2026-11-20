# IFC to CityGML research converter

Traceable IFC to CityGML 3.0 building conversion. Version 0.6.0 is the installable converter. Experimental V3 supports constrained repair and analytical testing. On the same 160 controlled inputs, accepted reference passes rose from 97 to 111 with constrained repair. Four accepted outputs still failed a reference check.

[Portfolio case study](https://www.daudee.com/work/ifc-to-citygml) · [160-input holdout results](results/v3-holdout-summary.json)

## Reproduce a small benchmark

Use Python 3.13 in a clean virtual environment. On Windows, run the following from
the checkout:

```sh
python -m pip install -e ".[dev,research]"
ifc-citygml setup-validator
python scripts/research_v3.py smoke --output smoke-benchmark
```

The smoke run generates four IFC fixtures and tests three conversion policies.
Expect `12/12 reference checks passed` and a report at
`smoke-benchmark/results/index.json`. Choose a new output directory for another
run. This check covers simple analytical fixtures. The linked holdout results
cover the separate 160-input evaluation.

On a non-Windows platform, first provide val3dity 2.7.0 through
`IFC_CITYGML_VAL3DITY`. See the [installation guide](docs/INSTALLATION.md) for
validator setup and converter commands. The full pipeline may require the
original source snapshots or a new acquisition from the documented providers.

## Data and attribution

The figures and summary use analytical benchmark geometry. The source bundle includes schema notices and their upstream manifest. External building files, native tool binaries and local review workbooks are acquired or built separately.

Project code has no separate reuse license. The cached OGC, W3C and OASIS schemas
retain their upstream notices and terms, as recorded in the
[schema bundle](src/ifc_citygml/resources/schemas/README.md) and
[source manifest](src/ifc_citygml/resources/schemas/manifest.json).

