# DARPA TC CDM Schema Notes

This document records the practical differences between CDM v18 (E3) and CDM v20
(E5) that affect Sentinel-Z's ingestion pipeline.

## Quick reference

| Property | CDM v18 (E3) | CDM v20 (E5) |
|---|---|---|
| Schema namespace | `com.bbn.tc.schema.avro.cdm18.*` | `com.bbn.tc.schema.avro.cdm20.*` |
| Year | April 2018 | May 2019 |
| Platforms | FreeBSD (CADETS), Ubuntu (THEIA), custom (TRACE), Windows (FiveDirections) | Same, plus ClearScope (Android) |
| Event record | Has `parameters` as `array<TagRunLengthTuple>` | Has expanded `parameters` union types |
| Subject record | `cid`, `parentSubject`, `cmdLine`, `properties` | Same + additional fields |
| FileObject | Simpler property map | Adds `peInfo`, `winFileObject` |
| MemoryObject | Present | Absent |
| UnnamedPipeObject | Present | Absent |
| SrcSinkObject | Present | Absent |
| Host record | Absent | Present (multi-host scenarios) |

## What Sentinel-Z does about it

`CDMParser._route_record` uses substring matching ("Event" in schema name,
etc.), so both versions are handled by the same routing code. The shared
record types (Event, Subject, FileObject, NetFlowObject, Principal) have
compatible field names across both versions where it matters for our
pipeline.

E3-only record types (`UnnamedPipeObject`, `MemoryObject`, `SrcSinkObject`)
are silently skipped during parsing. They don't contribute to the
behavioral signals our detector uses at the 1-second-window level.

The `detected_schema_version` attribute on `CDMParser` is set on the first
record we see (`cdm18` or `cdm20`). Downstream code can check this to:
- Look up the correct `DARPA_ATTACK_PERIODS` entry
- Warn if a mismatched schema appears (e.g., cdm20 records in an E3 ingest)

## Field-level differences (encountered in practice)

### Event records

Both versions:
```
{
  "type": "EVENT_OPEN" | "EVENT_READ" | ... ,
  "subject": <uuid>,
  "predicateObject": <uuid> | null,
  "timestampNanos": <int>,
  "properties": <map<string, string>>
}
```

v18-only nuances:
- `parameters` field uses `array<TagRunLengthTuple>` (a length-encoded run of tags)
- We don't parse `parameters` today (semantic risk engine ignores it). If we
  do in the future, expect divergent parsing logic per version.

v20-only nuances:
- Additional union members in `parameters` (CDM's evolution to support
  Windows-specific event types).

### Subject records

Both versions have:
- `uuid`, `type`, `cid`, `parentSubject`, `cmdLine`, `localPrincipal`

v18: `parameters` is `array<Value>` (limited type variety).
v20: `parameters` is a richer union (impact on `_extract_cmdline` should be tested).

### FileObject records

Both versions have:
- `uuid`, `type`, `baseObject` (containing `properties`)

v18: `baseObject.properties` is `map<string, string>` — path is at
`properties["path"]` or `properties["filename"]`.
v20: Adds Windows-specific subfields. Our `_extract_path` heuristic handles
both because it falls back gracefully.

## Reading the official schemas

Each engagement's GitHub repo includes the canonical Avro schema:
- E3: https://github.com/darpa-i2o/Transparent-Computing/tree/master/ta3-serialization-schema/avro/Engagement3
- E5: https://github.com/darpa-i2o/Transparent-Computing/tree/master/ta3-serialization-schema/avro/cdm20

When debugging an ingest failure, the first thing to check is whether the
Avro schema you're reading matches the engagement's CDM version.

## Known issues

### "Unknown schema type" warnings

If you see warnings about unknown record types during ingest, it usually means:
1. The .bin.gz file is from a non-standard exporter (e.g., custom TA1 team)
2. The CDM version is older than v18 (some early DARPA data uses CDM v10/v12)
3. The schema namespace was customized by the TA1 team

In all cases, the parser will skip unknown records and continue. Check the
parse-complete summary for record counts to verify you didn't lose too many.

### Timestamp parsing

DARPA `timestampNanos` is in UTC nanoseconds since the Unix epoch. Both versions.
We convert via `_convert_timestamp` in `auto_pipeline.py`. ISO8601 string
representation is used downstream.

### Property map flattening

Property maps in CDM are nested. Sentinel-Z doesn't fully flatten them today
(only the fields the semantic risk engine needs). If you add features that
depend on more property data, watch for inconsistencies between v18 and v20
property names — sometimes the same logical property uses different keys.

## When to add a new CDM version

If DARPA releases an Engagement 6 (or you encounter custom industry CDM
data), add the new version's marker string to `CDMParser.RECORD_TYPES` and
verify that `_route_record`'s substring matching still works. Add an explicit
`SCHEMA_V{N}_MARKER` constant if the version needs to be detected for
downstream logic.

Compatibility check:
```python
from src.sentinel_z.ingestion.auto_pipeline import CDMParser
p = CDMParser()
data = p.parse_file(Path("some_new_engagement_file.bin.gz"))
assert p.detected_schema_version in {"cdm18", "cdm20", "cdmNEW"}
```
