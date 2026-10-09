using System.Reflection;
using System.Text.Json;
using Flydigi.SharedResources.Data.Protobuf;

// Offline conversion only; no SDK initialization or controller operations.
if(args.Length != 1) throw new ArgumentException("Pass default_mapping_130.dat");
var factory = ControllerMappingConfigBeans.Parser.ParseFrom(File.ReadAllBytes(args[0]));
var sdk = Assembly.Load("Flydigi.ControllerSdk");
var mappingWriter = sdk.GetType("Flydigi.ControllerSDK.data.parser.MappingConfigParser")!
    .GetMethod("ParseConfigToArray", BindingFlags.NonPublic | BindingFlags.Static,
        null, new[]{typeof(ControllerMappingConfigBean),typeof(int)}, null)!;
var ledWriter = sdk.GetType("Flydigi.ControllerSDK.data.parser.LedConfigParser")!
    .GetNestedType("RgbConfigParserV30",BindingFlags.NonPublic)!
    .GetMethod("ParseConfigBeanToArray",BindingFlags.Public | BindingFlags.Static)!;
var macroWriter = sdk.GetType("Flydigi.ControllerSDK.data.parser.MacroConfigParser")!
    .GetMethod("ParseConfigToArray", BindingFlags.NonPublic | BindingFlags.Static,
        null, new[]{typeof(MacroConfigBean),typeof(int)}, null)!;
var output = factory.ControllerMappingConfigBean.Select(profile => {
    var chunks = (byte[][])mappingWriter.Invoke(null,new object[]{profile,20})!;
    var mapping = chunks.SelectMany(chunk=>chunk).ToArray();
    var lighting = (byte[])ledWriter.Invoke(null,new object[]{profile.LedConfigBean})!;
    var macroChunks = (byte[][])macroWriter.Invoke(null,new object[]{profile.MacroConfigBean,20})!;
    var macros = macroChunks.SelectMany(chunk=>chunk).ToArray();
    return new {profile=profile.CfgId, title=profile.Title, format=profile.ProtoVersion,
        mapping=Convert.ToHexString(mapping).ToLowerInvariant(),
        lighting=Convert.ToHexString(lighting).ToLowerInvariant(),
        macros=Convert.ToHexString(macros).ToLowerInvariant()};
});
Console.WriteLine(JsonSerializer.Serialize(output,new JsonSerializerOptions{WriteIndented=true}));
