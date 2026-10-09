# Global-setting command reference

This harness calls Space Station 4.2.0.9's command factories with synthetic
values. It generates every choice exposed by Flydigi Control's global-settings
page: seven toggles, five precision settings, three center sensitivities and six
sleep durations. No vendor binaries are distributed here.

```sh
dotnet run --project experimental/settings-reference/SettingsReference.csproj \
  -p:VendorDir=/absolute/path/to/extracted/assemblies
```

The program creates only an uninitialized controller model with the NewXInput
type set. It does not initialize the SDK, enumerate devices or send commands.
The generated JSON is committed as `tests/fixtures/global-settings-vendor.json`.
Tests compare it with our encoder and require coverage of every offered choice.

The SDK prefixes packets with its endpoint byte, `06`. The harness removes that
byte and excludes USB padding; it retains the command, length, payload and
checksum. Linux HID report IDs, padding and transport behavior are checked
separately. Matching these command bytes does not prove firmware support or
persistence across power loss.

Report rate is intentionally excluded. Space Station's settings renderer shows
that selector only for `f4`, not `f5`. It sends 1/2/3/4 for 1000/500/250/125 Hz;
the IPC handler forwards the number unchanged, while the SDK enum names those
rates with 1/2/4/8. There is no conversion in the repository or command factory.
A shared SDK command is not evidence that the Vader 5 supports the selector.
