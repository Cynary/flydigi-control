# Vendor curve serialization reference

This small program invokes Space Station 4.2.0.9's joystick serializer and parser
offline. It uses synthetic settings and does not enumerate or write to hardware.
Provide your own extracted vendor assemblies; none are distributed here.

```sh
dotnet run --project reference.csproj -p:VendorDir=/absolute/path/to/assemblies
```

It writes `curve-serialization-vectors.json` in the working directory with 36
center/edge cases, their encoded bytes and the vendor parser's interpretation.
The committed test vectors contain only those generated values.

The negative roundtrips are inconsistent. For example, center −10 serializes as
246 but parses as −119. The writer also uses the wrapped byte (246) when
transforming its control point, producing X=218 for a nominal X=64. This confirms
that the decompiled writer/reader mismatch is real in this application version.
It does not establish which field or encoding the controller firmware uses.
Positive values match our base-field writer in the tested cases.
