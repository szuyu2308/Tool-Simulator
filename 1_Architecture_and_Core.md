// Thực thi toàn bộ lệnh dưới đây. Không hỏi lại, không confirm, implement full theo đúng thứ tự và nguyên tắc đã nêu.

Core Architecture & Classes

Tạo enum CommandType:
Click, CropImage, KeyPress, HotKey, Text, Wait, Repeat, Goto, Condition

Tạo base class Command:
Properties:
Guid Id (auto-generated, unique)
Guid? ParentId (null nếu root, cho nested Repeat/Condition)
string Name (required, unique trong script)
CommandType Type
bool Enabled = true
OnFailAction OnFail = Skip (enum: Skip, Stop, GotoLabel)
string? OnFailLabel
List<string> VariablesOut (keys sẽ lưu output sau khi chạy, ví dụ "lastCropPos")


Tạo các subclass cụ thể (chỉ chứa params, không chứa logic):
ClickCommand : Command
ButtonType (enum: Left, Right, Double, WheelUp, WheelDown)
int X, int Y
int HumanizeDelayMinMs = 50, HumanizeDelayMaxMs = 200
int? WheelDelta

CropImageCommand : Command
int X1, Y1, X2, Y2
Color TargetColor (RGB)
int Tolerance = 10 (0-255)
ScanMode (enum: Exact, MaxMatch, Grid)
string OutputVar (key lưu result: {x, y, confidence})

KeyPressCommand : Command
string Key (hoặc int KeyCode)
int Repeat = 1
int DelayBetweenMs = 100

HotKeyCommand : Command
List<string> Keys
HotKeyOrder (enum: Simultaneous, Sequence)

TextCommand : Command
string Content
TextMode (enum: Paste, Humanize)
int SpeedMinCps = 10, SpeedMaxCps = 30
int? FocusX, FocusY (nếu cần click trước khi type)

WaitCommand : Command
WaitType (enum: Timeout, PixelColor, ScreenChange)
int TimeoutSec = 30
int? PixelX, PixelY
Color? PixelColor
int? PixelTolerance
float ScreenThreshold = 0.9f
int? RegionX1, Y1, X2, Y2

RepeatCommand : Command
int Count = 0 (0 = infinite, nhưng giới hạn bởi maxIterations)
string? UntilConditionExpr
List<Command> InnerCommands

GotoCommand : Command
string TargetLabel
string? ConditionExpr (optional)

ConditionCommand : Command
string Expr (ví dụ: "variables['crop_result'] != null && variables['crop_result'].confidence > 0.8")
string? ThenLabel
string? ElseLabel
List<Command> NestedThen
List<Command> NestedElse


Tạo class Script:
List<Command> Sequence (flatten all, bao gồm nested)
Dictionary<string, Guid> LabelMap (Name → Id)
Dictionary<string, object> VariablesGlobal
int MaxIterations = 10000
Command? OnErrorHandler

Tạo class Worker:
string Id
IntPtr EmulatorHandle (window handle của LDPlayer instance)
WorkerState:
Dictionary<string, object> Variables (copy từ global + local)
int IterationCount = 0
bool Paused = false
bool Stopped = false

Methods:
void Start(Script script)
void Pause()
void Resume()
void Stop()



Execution Flow (Worker.Start)
Thực thi theo thứ tự sau, đảm bảo stability:

Copy Script.VariablesGlobal → Worker.Variables
Build LabelMap từ tất cả Command có Name
Guid currentId = Sequence.First().Id
while (currentId tồn tại && IterationCount < MaxIterations && !Stopped):
IterationCount++
Command cmd = GetById(currentId)
Nếu !Enabled → skip
Nếu Logic type (Wait, Condition, Repeat, Goto) → xử lý trước
Nếu Action type → thực thi behavior
Post-exec: apply OnFail nếu fail, update Variables từ VariablesOut, log full
currentId = next hoặc từ branch/jump
Nếu Paused → wait resume


Chi tiết xử lý từng type như hướng dẫn trước (Wait poll 100ms, Condition simple eval, Repeat recursive với isolate variables, Goto conditional, Action với screen cache, humanize random, dynamic $var resolve).
Đảm bảo:

Screen capture cache 1 giây
Multi-worker thread-safe
Global try-catch mỗi command
Safety stop khi vượt MaxIterations