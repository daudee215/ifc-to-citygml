# IFC to CityGML research converter

Traceable IFC to CityGML 3.0 building conversion. Version 0.6.0 is the installable converter. Experimental V3 supports constrained repair and analytical testing. On the same 160 controlled inputs, accepted reference passes rose from 97 to 111 with constrained repair. Four accepted outputs still failed a reference check.

[Portfolio case study](https://www.daudee.com/work/ifc-to-citygml)

## Run

Use Python 3.13 in a clean virtual environment. Full pipeline runs may need the original source snapshots or a new acquisition from the documented providers.

```sh
python -m pip install -e .[dev]
ifc-citygml --help
ifc-citygml setup-validator
python scripts/research_v3.py --help
python -m pytest -q tests/test_v3_conversion.py tests/test_v3_annotation_scope.py
```

On a non-Windows platform, supply val3dity 2.7.0 via `IFC_CITYGML_VAL3DITY` and follow the [installation guide](docs/INSTALLATION.md).

## Data and attribution

The figures and summary use analytical benchmark geometry. The source bundle includes schema notices and their upstream manifest. External building files, native tool binaries and local review workbooks are acquired or built separately.

