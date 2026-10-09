using System.Reflection;
using System.Text.Json;
using Flydigi.SharedResources.Data.Protobuf;

// Invokes installed vendor code offline: no device enumeration or HID access.
var root=Assembly.Load("Flydigi.ControllerSdk").GetType("Flydigi.ControllerSDK.data.parser.MappingConfigParser")!;
var baseParser=root.GetNestedType("MappingConfigParserV30",BindingFlags.Public)!;
var extraParser=root.GetNestedType("MappingConfigParserV31",BindingFlags.Public)!;
var flags=BindingFlags.NonPublic|BindingFlags.Static;
var serializeBase=baseParser.GetMethod("ParseJoystickConfigToArray",flags)!;
var readBase=baseParser.GetMethod("ParseToJoystickConfig",flags)!;
var serializeExtra=extraParser.GetMethod("ParseJoystickConfigExtraToData",flags)!;
var readExtra=extraParser.GetMethod("ParseToJoystickConfig",flags)!;
var results=new List<object>();
foreach(int center in new[]{-100,-50,-10,-1,0,1,5,10,25,50,75,100}) {
  foreach(int edge in new[]{-10,0,10}) {
    // Parse a synthetic default block to obtain the SDK's complete bean shape.
    byte[] initial={0,0,64,64,127,127,127,0,0,64,64,127,127,127};
    var settings=(JoystickConfigBeans)readBase.Invoke(null,new object[]{initial,false})!;
    foreach(var stick in new[]{settings.LeftJoystickParam,settings.RightJoystickParam}) {
      stick.MapTypeJoystick.Center=center;stick.MapTypeJoystick.Edge=edge;
      for(int i=0;i<9;i++)stick.MapTypeJoystick.SensitivityConfig.Points.Add(50+i*12);
    }
    var encodedBase=(byte[])serializeBase.Invoke(null,new object[]{settings,false})!;
    var encodedExtra=(byte[])serializeExtra.Invoke(null,new object[]{settings})!;
    var decoded=(JoystickConfigBeans)readBase.Invoke(null,new object[]{encodedBase,false})!;
    readExtra.Invoke(null,new object[]{decoded,encodedExtra});
    results.Add(new{center,edge,base_hex=Convert.ToHexString(encodedBase).ToLowerInvariant(),
      extra_hex=Convert.ToHexString(encodedExtra).ToLowerInvariant(),
      read_center=decoded.LeftJoystickParam.MapTypeJoystick.Center,
      read_edge=decoded.LeftJoystickParam.MapTypeJoystick.Edge});
  }
}
File.WriteAllText("curve-serialization-vectors.json",JsonSerializer.Serialize(results,new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine($"Wrote {results.Count} vendor writer/reader cases; no hardware was accessed.");
