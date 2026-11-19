# Cached official schemas

`manifest.json` pins the source URL and SHA-256 hash of each cached schema. Upstream
bytes are preserved, including copyright/licence notices. OGC, W3C and OASIS
dependencies retain their respective notices and terms; they are not relicensed as
project code. See each upstream schema and its publisher's terms.

The dependency closure was fetched from the official published Building 3.0 schema
using `scripts/fetch_schemas.py`. The local XML resolver verifies hashes before
loading imports and does not fetch remote imports during validation.
