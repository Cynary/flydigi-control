# Checking the Default lighting preset

This harness reads an extracted Space Station factory profile with the vendor's
protobuf parser, then serializes its lighting with the vendor SDK. It neither
connects to a controller nor changes Windows settings. Vendor assemblies and
configuration files are not included.

Use .NET 10 and assemblies extracted from Space Station 4.2.0.9:

```sh
dotnet run --project experimental/lighting-reference/LightingReference.csproj \
  -p:VendorDir=/absolute/path/to/extracted/assemblies -- \
  /absolute/path/to/Configs/Controller/f5/default/default_mapping_130.dat
```

The JSON result contains each profile's geometry, defaults and complete lighting
bytes. `tests/test_lighting.py` compares SHA-256 digests of the animation bytes
with these independent results. Header fields are checked separately because our
editor deliberately preserves the controller's grip-sync and reserved fields.

The reference file contains four profiles: profile 1's animation is distinct;
profiles 2–4 share an animation. This is evidence of Space Station's reset values,
not a measurement of the controller's factory flash or its behavior after saving.
