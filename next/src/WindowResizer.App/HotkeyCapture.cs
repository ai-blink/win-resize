using System.Windows.Input;
using WindowResizer.Core.Hotkeys;

namespace WindowResizer.App;

/// <summary>눌린 키 하나를 <see cref="HotkeyCapture.Interpret"/> 가 어떻게 읽었는가.</summary>
public enum CaptureOutcome
{
    /// <summary>가로채지 않는다(Tab 등). 감지 칸을 벗어나는 데 쓰는 키다.</summary>
    PassThrough,

    /// <summary>수정키만 눌렸다. 주 키를 기다린다.</summary>
    Waiting,

    /// <summary>이름을 붙일 수 없는 키라 무시했다. 계속 기다린다.</summary>
    Ignored,

    /// <summary>Delete/Backspace 를 수정키 없이 눌러 지운다.</summary>
    Cleared,

    /// <summary>조합이 정해졌다.</summary>
    Set,
}

/// <summary>
/// 감지 규칙(D-026). 화면 요소와 무관하게 "이 키와 수정키가 눌렸을 때 어떻게 할까"만 정한다.
///
/// - 수정키만 누른 동안은 기다린다. 주 키가 눌리는 순간 확정한다.
/// - Delete / Backspace 를 수정키 없이 누르면 지운다(그 둘만의 단축키는 없다).
/// - Tab 과 Shift+Tab, Alt+F4 는 가로채지 않는다: 키보드로 칸을 벗어나고 창을 닫을 수 있어야 한다.
/// - 이름을 붙일 수 없는 키(<see cref="HotkeyCombination.Format"/> 이 null)는 무시한다.
/// </summary>
public static class HotkeyCapture
{
    public static CaptureOutcome Interpret(Key key, ModifierKeys modifiers, out string? text)
    {
        text = null;
        if (key is Key.Tab && (modifiers & (ModifierKeys.Control | ModifierKeys.Alt | ModifierKeys.Windows)) == 0)
            return CaptureOutcome.PassThrough;
        if (key is Key.F4 && modifiers == ModifierKeys.Alt) return CaptureOutcome.PassThrough;

        if (key is Key.LeftCtrl or Key.RightCtrl or Key.LeftAlt or Key.RightAlt or Key.LeftShift or Key.RightShift
            or Key.LWin or Key.RWin or Key.None)
            return CaptureOutcome.Waiting;

        if (modifiers == ModifierKeys.None && key is Key.Delete or Key.Back)
        {
            text = "";
            return CaptureOutcome.Cleared;
        }

        var combination = new HotkeyCombination(ToHotkeyModifiers(modifiers), KeyInterop.VirtualKeyFromKey(key)).Format();
        if (combination is null) return CaptureOutcome.Ignored;

        text = combination;
        return CaptureOutcome.Set;
    }

    private static HotkeyModifiers ToHotkeyModifiers(ModifierKeys modifiers)
    {
        var result = HotkeyModifiers.None;
        if ((modifiers & ModifierKeys.Control) != 0) result |= HotkeyModifiers.Control;
        if ((modifiers & ModifierKeys.Alt) != 0) result |= HotkeyModifiers.Alt;
        if ((modifiers & ModifierKeys.Shift) != 0) result |= HotkeyModifiers.Shift;
        if ((modifiers & ModifierKeys.Windows) != 0) result |= HotkeyModifiers.Win;
        return result;
    }
}
