# Factory profile reference

This offline harness parses `default_mapping_130.dat` from Space Station 4.2.0.9
and invokes its mapping, lighting and macro serializers. It does not open any
controller or initialize the hardware SDK. Supply your own extracted assemblies:

```sh
dotnet run --project experimental/profile-reference/ProfileReference.csproj \
  -p:VendorDir=/absolute/path/to/extracted/assemblies -- \
  /absolute/path/to/Configs/Controller/f5/default/default_mapping_130.dat
```

The four outputs use mapping format 3.2. The SDK's NewXInput writer serializes
84 × 20 bytes for mapping, but the controller's captured read reports 42 × 20
bytes. The trailing 840 SDK bytes are all FF. The first 840 bytes contain the
known settings. Our restore is restricted to the captured firmware and geometry;
it never expands the controller's reported extent to write that extra padding.

Lighting is 320 bytes. Each factory macro bank is 1620 bytes with version 0x100,
zero records and FF padding. Both are serialized using the same sizes as the
vendor's NewXInput writer. The packaged data contains the first 840 mapping bytes
and lighting for each profile; the empty macro bank is generated explicitly.
Tests compare all three sections with digests from these SDK outputs, normalizing
only the two-byte mapping save version, which must be newly assigned on Apply.

These are Space Station's profile-reset values, not a dump of factory flash.
The app resets only the active PC profile and backs up its current contents;
it does not invoke a firmware-wide reset or change global calibration switches.
Hardware reset/undo and retention after power-off remain unverified.
