using System.Reflection;
using System.Text.Json;
using Flydigi.SharedResources.Data.Protobuf;

var sdk = Assembly.Load("Flydigi.ControllerSdk");
var parser = sdk.GetType("Flydigi.ControllerSDK.data.parser.MacroConfigParser")!.GetNestedType("MacroConfigParserV10", BindingFlags.NonPublic)!;
var serialize = parser.GetMethod("ParseConfigBeanToArray", BindingFlags.Public | BindingFlags.Static)!;
var parse = parser.GetMethod("ParseDataToConfigBean", BindingFlags.NonPublic | BindingFlags.Static)!;
var outputs = new List<object>();
foreach (int count in new[]{0,1,2,10}) {
    var bank = new MacroConfigBean { Version = 256 };
    for(int i=0;i<count;i++) {
        var macro = new MacroItem { KeyId=(ControllerKey)(i+4), Type=(MacroEnableType)(1+i%3), Interval=10+i*5, CfgName=i==1?"é猫":"Test"+i };
        macro.Actions.Add(new MacroAction { Duration=0,KeyId=ControllerKey.A,Event=MacroActionEvent.Press });
        macro.Actions.Add(new MacroAction { Duration=37+i,KeyId=ControllerKey.A,Event=MacroActionEvent.Release });
        macro.Actions.Add(new MacroAction { Duration=258+i,KeyId=ControllerKey.JoystickRight,Event=MacroActionEvent.LeftJoystick });
        macro.Actions.Add(new MacroAction { Duration=14,KeyId=ControllerKey.JoystickCenter,Event=MacroActionEvent.RightJoystick });
        macro.Count=macro.Actions.Count;
        bank.Macros.Add(macro);bank.Interval.Add(macro.Interval);
    }
    byte[] encoded=(byte[])serialize.Invoke(null,new object[]{bank})!;
    var decoded=new MacroConfigBean();
    parse.Invoke(null,new object[]{decoded,encoded});
    if(decoded.Macros.Count!=count)throw new Exception("Reference roundtrip failed");
    outputs.Add(new{count,hex=Convert.ToHexString(encoded).ToLowerInvariant()});
}
File.WriteAllText("macro-vendor-vectors.json",JsonSerializer.Serialize(outputs,new JsonSerializerOptions{WriteIndented=true}));
Console.WriteLine("Wrote four serializer vectors and checked the vendor parser.");
