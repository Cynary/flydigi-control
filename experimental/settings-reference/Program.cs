using System.Reflection;
using System.Runtime.CompilerServices;
using System.Text.Json;

// Command construction only. No SDK initialization, device discovery or I/O.
var sdk = Assembly.Load("Flydigi.ControllerSdk");
var controllerType = sdk.GetType("Flydigi.ControllerSDK.data.model.Controller")!;
var controller = RuntimeHelpers.GetUninitializedObject(controllerType);
var typeField = controllerType.GetField("<ControllerType>k__BackingField", BindingFlags.Instance | BindingFlags.NonPublic)!;
typeField.SetValue(controller, Enum.Parse(typeField.FieldType, "NewXInput"));
var vectors = new List<object>();
void Record(string name, string factoryName, object value) {
    var factory = sdk.GetType("Flydigi.ControllerSDK.data.command.setting." + factoryName)!;
    var create = factory.GetMethod("CreateCommand", BindingFlags.Public | BindingFlags.Static)!;
    var parameters = create.GetParameters();
    var inputs = new object[parameters.Length];
    inputs[0] = controller;
    inputs[1] = parameters[1].ParameterType.IsEnum ? Enum.ToObject(parameters[1].ParameterType, value) : value;
    var command = create.Invoke(null, inputs)!;
    var packet = (byte[])command.GetType().GetMethod("CreateCommand")!.Invoke(command, null)!;
    if(packet[0] != 6 || packet[1] != 0x5a || packet[2] != 0xa5) throw new Exception("Unexpected endpoint or packet header");
    // Strip the SDK endpoint byte and exclude unused USB padding.
    var body = packet.AsSpan(1, packet[4] + 3);
    vectors.Add(new {name, value, hex=Convert.ToHexString(body).ToLowerInvariant()});
}
var toggles = new Dictionary<string,string> {
    ["profile_hotkeys"]="EnableQuickSwitchConfigCommandFactory",
    ["home_button"]="EnableXboxHomeButtonCommandFactory",
    ["motion_filter"]="EnableMotionDebounceCommandFactory",
    ["turbo"]="EnableMappingSwitchCommandFactory",
    ["stick_filter"]="EnableJoystickDebounceCommandFactory",
    ["auto_calibration"]="EnableJoystickAutoCalibrationCommandFactory",
    ["rebound"]="EnableJoystickReboundCommandFactory",
};
foreach(var (name,factory) in toggles) foreach(var value in new[]{false,true}) Record(name,factory,value);
foreach(var value in new[]{1,2,3,4,5}) Record("precision","UpdateJoystickPrecisionCommandFactory",value);
foreach(var value in new[]{14,17,19}) Record("sensitivity","UpdateJoystickSensitivityCommandFactory",value);
foreach(var value in new[]{0,1,5,15,60,180}) Record("sleep","UpdateSleepTimeCommandFactory",value);
Console.WriteLine(JsonSerializer.Serialize(vectors,new JsonSerializerOptions{WriteIndented=true}));
