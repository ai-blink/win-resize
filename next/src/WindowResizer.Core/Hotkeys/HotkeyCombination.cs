namespace WindowResizer.Core.Hotkeys;

/// <summary>Win32 <c>MOD_*</c> 값과 같다. <c>RegisterHotKey</c> 에 그대로 넘긴다.</summary>
[Flags]
public enum HotkeyModifiers
{
    None = 0,
    Alt = 0x0001,
    Control = 0x0002,
    Shift = 0x0004,
    Win = 0x0008,
}

/// <summary>
/// 편집 창이 저장하는 단축키 문자열(<c>"Ctrl+Alt+E"</c>)을 등록 값으로 바꾼다.
/// 규칙은 PyQt5 <c>parse_hotkey_combination</c> 과 같다:
/// 수정키는 대소문자 무시, 같은 수정키 두 번은 오류, 주 키는 정확히 하나.
/// </summary>
public readonly record struct HotkeyCombination(HotkeyModifiers Modifiers, int VirtualKey)
{
    private static readonly Dictionary<string, HotkeyModifiers> ModifierNames = new(StringComparer.OrdinalIgnoreCase)
    {
        ["ctrl"] = HotkeyModifiers.Control,
        ["alt"] = HotkeyModifiers.Alt,
        ["shift"] = HotkeyModifiers.Shift,
        ["win"] = HotkeyModifiers.Win,
    };

    private static readonly Dictionary<string, int> SpecialKeys = new(StringComparer.OrdinalIgnoreCase)
    {
        ["space"] = 0x20,
        ["enter"] = 0x0D,
        ["tab"] = 0x09,
        ["backspace"] = 0x08,
        ["delete"] = 0x2E,
        ["home"] = 0x24,
        ["end"] = 0x23,
        ["page up"] = 0x21,
        ["page down"] = 0x22,
        ["left"] = 0x25,
        ["up"] = 0x26,
        ["right"] = 0x27,
        ["down"] = 0x28,
        ["insert"] = 0x2D,
        ["escape"] = 0x1B,
        ["esc"] = 0x1B,
    };

    /// <summary>
    /// 해석한다. 실패하면 이유를 담은 <see cref="FormatException"/>.
    ///
    /// PyQt5 와 한 곳이 다르다: 한 글자 주 키는 <b>ASCII 영문/숫자만</b> 받는다. Python 의
    /// <c>isalnum()</c> 은 한글 같은 글자도 통과시키지만 그 코드는 가상 키 범위(1-255) 밖이라
    /// 등록 단계에서 어차피 실패했다. 여기서는 해석 단계에서 이유를 말하고 거절한다.
    /// </summary>
    public static HotkeyCombination Parse(string? combination)
    {
        if (string.IsNullOrWhiteSpace(combination))
            throw new FormatException("단축키가 비어 있다");

        var modifiers = HotkeyModifiers.None;
        int? key = null;

        foreach (var raw in combination.Split('+'))
        {
            var name = raw.Trim();
            if (ModifierNames.TryGetValue(name, out var modifier))
            {
                if ((modifiers & modifier) != 0) throw new FormatException("같은 수정키가 두 번 있다: " + name);
                modifiers |= modifier;
                continue;
            }

            if (key is not null) throw new FormatException("주 키는 정확히 하나여야 한다");
            key = MainKey(name);
        }

        return key is null
            ? throw new FormatException("주 키가 없다")
            : new HotkeyCombination(modifiers, key.Value);
    }

    /// <summary>
    /// 저장 문자열로 되돌린다(<see cref="Parse"/> 의 역). 수정키 순서는 Ctrl, Alt, Shift, Win 이다.
    /// 이름을 붙일 수 없는 가상 키(마우스 버튼, 미디어 키 등)면 null.
    /// </summary>
    public string? Format()
    {
        string? key = null;
        if (VirtualKey is >= 'A' and <= 'Z' || VirtualKey is >= '0' and <= '9') key = ((char)VirtualKey).ToString();
        else if (VirtualKey is >= 0x70 and <= 0x87) key = "F" + (VirtualKey - 0x6F);
        else key = SpecialKeyNames.GetValueOrDefault(VirtualKey);
        if (key is null) return null;

        var parts = new List<string>();
        if ((Modifiers & HotkeyModifiers.Control) != 0) parts.Add("Ctrl");
        if ((Modifiers & HotkeyModifiers.Alt) != 0) parts.Add("Alt");
        if ((Modifiers & HotkeyModifiers.Shift) != 0) parts.Add("Shift");
        if ((Modifiers & HotkeyModifiers.Win) != 0) parts.Add("Win");
        parts.Add(key);
        return string.Join("+", parts);
    }

    /// <summary>되돌릴 때 쓰는 이름. <c>esc</c> 같은 별칭은 <see cref="SpecialKeys"/> 에서만 받고 여기서는 내지 않는다.</summary>
    private static readonly Dictionary<int, string> SpecialKeyNames = new()
    {
        [0x20] = "Space", [0x0D] = "Enter", [0x09] = "Tab", [0x08] = "Backspace", [0x2E] = "Delete",
        [0x24] = "Home", [0x23] = "End", [0x21] = "Page Up", [0x22] = "Page Down",
        [0x25] = "Left", [0x26] = "Up", [0x27] = "Right", [0x28] = "Down",
        [0x2D] = "Insert", [0x1B] = "Escape",
    };

    public static bool TryParse(string? combination, out HotkeyCombination result)
    {
        try
        {
            result = Parse(combination);
            return true;
        }
        catch (FormatException)
        {
            result = default;
            return false;
        }
    }

    private static int MainKey(string name)
    {
        if (name.Length == 1 && char.IsAsciiLetterOrDigit(name[0]))
            return char.ToUpperInvariant(name[0]);

        if (name.Length >= 2 && (name[0] == 'f' || name[0] == 'F') && int.TryParse(name.AsSpan(1), out var f)
            && name[1..].All(char.IsAsciiDigit))
        {
            return f is >= 1 and <= 24
                ? 0x6F + f
                : throw new FormatException("지원하지 않는 기능 키: " + name);
        }

        return SpecialKeys.TryGetValue(name, out var code)
            ? code
            : throw new FormatException("지원하지 않는 키: " + name);
    }
}
