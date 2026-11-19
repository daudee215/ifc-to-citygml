# Install and run version 0.6

The wheel contains seven conversion profiles and the complete pinned 62-file schema
closure. Runtime resources are loaded from the installed package independently of
the working directory. IFC benchmark models and validator binaries are not embedded.

## Tested environment and installation

Windows x64, Python 3.13. Other platforms may supply native val3dity 2.7.0, but are
not covered by the current clean-install verification.

From the delivered project directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --constraint requirements.lock.txt dist/ifc_citygml-0.6.0-py3-none-any.whl
.\.venv\Scripts\ifc-citygml.exe --version
.\.venv\Scripts\ifc-citygml.exe doctor
```

The constraint file pins transitive dependencies used in the verified run. Doctor
checks resource hashes, schema compilation, profiles and the actual validator.
It returns 2 with `needs_validator` until independent validation is configured.

## Configure the validator

Explicit online setup on Windows:

```powershell
.\.venv\Scripts\ifc-citygml.exe setup-validator
.\.venv\Scripts\ifc-citygml.exe doctor
```

The installer verifies the upstream archive before extraction. Its default directory
is `%LOCALAPPDATA%/ifc-citygml/tools/val3dity/2.7.0/`. `IFC_CITYGML_CACHE_DIR` changes
the cache root; setup's `--directory` chooses an explicit destination. The original
archive and installed-file hashes are retained.

The Windows release needs a GCC runtime DLL beyond its included files. The validation
subprocess discovers Git for Windows' runtime or uses `VAL3DITY_RUNTIME_DIR`. Actual
runtime hashes are recorded; the permanent PATH is not changed. Doctor reports an
unavailable/incompatible runtime instead of claiming validation success.

An existing native executable can be selected per command:

```powershell
ifc-citygml doctor --validator C:/tools/val3dity/val3dity.exe
ifc-citygml convert C:/models/building.ifc --profile source --validator C:/tools/val3dity/val3dity.exe --output C:/outputs/building.gml
```

`IFC_CITYGML_VAL3DITY` provides the equivalent environment setting. An explicit
missing executable does not silently fall back. The integration requires version
2.7.0 and records the actual executable hash.

Offline installation accepts the original upstream archive:

```powershell
ifc-citygml setup-validator --archive C:/downloads/val3dity-win64.zip --directory C:/tools/val3dity
```

Its SHA-256 must be `cf8d3f025cd52aafc9ea370296a2430baa4aa39ce44a8b3ba1d8b3a540d8a5a7`.
The release has nested ZIP packaging; an extracted inner ZIP is not interchangeable
with the pinned original. Setup handles the nesting.

## Run from any folder

Activate the environment or use its executable's absolute path:

```powershell
ifc-citygml inspect C:/models/building.ifc --report C:/outputs/inspection.json
ifc-citygml convert C:/models/building.ifc --profile source --output C:/outputs/building.gml
ifc-citygml validate C:/outputs/building.gml --report C:/outputs/validation.json
```

Built-in profiles are `block`, `exterior`, `source` and `map`; `--config` accepts
custom JSON and is mutually exclusive with `--profile`. Map conversion requires
explicit IFC4 metadata and a complete three-axis metre CRS.

Version 0.5 also includes `engineering-block`, `engineering-exterior` and
`engineering-source`. These opt-in profiles preserve original IFC4 map metadata
without applying it and output explicitly labelled engineering coordinates. See
[the frame and provenance contract](ENGINEERING_FRAME.md). They do not establish
geographic placement or a geographic height datum.

Blocks retain bounded local checks if independent tooling is unavailable, with its
state visible in the CLI/report. Surface profiles require independent target-type
checks. Their stronger Solid diagnostic and source/envelope distinction remain visible.

Version 0.6 block profiles explicitly select physical Body representations and
record annotation-only omissions. Mixed products retain their physical bodies;
invalid bodies remain strict failures. See [the representation policy](BLOCK_REPRESENTATIONS.md).

## Build and verify

```powershell
.\.venv\Scripts\python.exe scripts/sync_package_resources.py
.\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation . --wheel-dir dist
.\.venv\Scripts\python.exe scripts/verify_wheel_install.py --wheel dist/ifc_citygml-0.6.0-py3-none-any.whl
```

The verification uses a fresh venv and managed cache in the system temporary
directory, outside the checkout. It tests installed conversion, validation, map
placement and failed-case benchmarks, comparing GML bytes with the source installation.
See [the generated verification report](../results/v0_6/packaging/CLEAN_INSTALL_VERIFICATION.md)
and [benchmark manifest instructions](BENCHMARK_CLI.md).

After rerunning the research benchmark and summary, `scripts/audit_release.py`
checks that the verified wheel still matches the current code/resources, checks
every current input/output hash and compares successful GML files with the retained
v0.3 baseline. See [release audit](../results/v0_6/packaging/RELEASE_AUDIT.md).

The prior v0.4 wheel, original benchmark directories and clean-install evidence
remain available. `releases/0.4.0/source.zip` preserves its source/resources and
`RELEASE_MANIFEST.json` records artifact hashes. `scripts/preserve_release.py`
verifies those frozen artifacts without overwriting them. New evaluation scripts
use separate `results/v0_6` directories.

The verified v0.5 release is also frozen under `releases/0.5.0`; verify its original
artifacts with `scripts/preserve_release.py --version 0.5.0`.
