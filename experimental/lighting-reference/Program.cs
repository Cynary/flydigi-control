using System.Reflection;
using System.Text.Json;
using Flydigi.SharedResources.Data.Protobuf;

// Read the user's extracted factory profile through the vendor's own parser.
// No vendor assemblies or profiles are distributed with this harness.
if (args.Length != 1) throw new ArgumentException("Pass default_mapping_130.dat");
var profiles = ControllerMappingConfigBeans.Parser.ParseFrom(File.ReadAllBytes(args[0]));
var parser = Assembly.Load("Flydigi.ControllerSdk")
    .GetType("Flydigi.ControllerSDK.data.parser.LedConfigParser")!
    .GetNestedType("RgbConfigParserV30", BindingFlags.NonPublic)!;
var serialize = parser.GetMethod("ParseConfigBeanToArray", BindingFlags.Public | BindingFlags.Static)!;
var output = profiles.ControllerMappingConfigBean.Select(profile => {
    var led = profile.LedConfigBean;
    return new {profile = profile.CfgId, version = led.Version, zones = led.RgbNum,
        frames = led.LedGroup.Count, mode = led.LedMode,
        loopStart = led.LoopStart, loopEnd = led.LoopEnd,
        period = led.LoopTime, brightness = led.Brightness,
        hex = Convert.ToHexString((byte[])serialize.Invoke(null, new object[]{led})!).ToLowerInvariant()};
});
Console.WriteLine(JsonSerializer.Serialize(output, new JsonSerializerOptions{WriteIndented=true}));
