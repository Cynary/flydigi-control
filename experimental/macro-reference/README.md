# Macro serializer reference check

This harness calls only the vendor SDK's macro serializer and parser; it does
not access hardware. Supply your extracted Space Station 4.2.0.9 assemblies
(`Flydigi.ControllerSdk.dll`, `Flydigi.SharedResources.dll`, `Flydigi.Basic.dll`
and `Google.Protobuf.dll`). No vendor code is included here.

With .NET 10 installed, run from this directory:

```sh
dotnet run --project reference.csproj -p:VendorDir=/path/to/assemblies
```

It writes `macro-vendor-vectors.json`. The checked-in fixtures were generated
this way and then compared with our encoder by `tests/test_macro_bank.py`.
The synthetic version value 256 is a test input, not a claim that a hardware
capture has confirmed the bank version on every controller.
