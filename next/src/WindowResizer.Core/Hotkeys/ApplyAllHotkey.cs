using System.Text.Json;

namespace WindowResizer.Core.Hotkeys;

/// <summary>
/// 전체 적용 전역 단축키(프로필과 무관한 하나). <see cref="Combination"/> 은 <c>"Ctrl+Alt+E"</c> 같은 저장 문자열이다.
/// 꺼져 있어도 조합은 남긴다 - 다시 켤 때 다시 입력하지 않게.
/// </summary>
public sealed record ApplyAllHotkey(bool Enabled, string Combination)
{
    public static readonly ApplyAllHotkey Off = new(false, "");

    /// <summary>
    /// PyQt5 <c>application_hotkeys.json</c> 에서 가져온다:
    /// <c>{"apply_all_profiles": {"modifiers": &lt;MOD 플래그&gt;, "key_code": &lt;VK&gt;, "enabled": ...}}</c>.
    /// 읽지 못하거나 조합으로 바꿀 수 없는 가상 키면 null - 가져올 것이 없다.
    /// </summary>
    public static ApplyAllHotkey? FromLegacyJson(string json)
    {
        try
        {
            using var document = JsonDocument.Parse(json);
            if (document.RootElement.ValueKind != JsonValueKind.Object ||
                !document.RootElement.TryGetProperty("apply_all_profiles", out var entry) ||
                entry.ValueKind != JsonValueKind.Object)
                return null;

            if (!TryInt(entry, "modifiers", out var modifiers) || !TryInt(entry, "key_code", out var keyCode)) return null;

            var text = new HotkeyCombination((HotkeyModifiers)(modifiers & 0x000F), keyCode).Format();
            if (text is null) return null;

            var enabled = entry.TryGetProperty("enabled", out var flag) && flag.ValueKind == JsonValueKind.True;
            return new ApplyAllHotkey(enabled, text);
        }
        catch (JsonException)
        {
            return null;
        }
    }

    // TryGetInt32 는 숫자가 아닌 값에 false 가 아니라 예외를 던진다. 종류를 먼저 본다.
    private static bool TryInt(JsonElement entry, string name, out int value)
    {
        value = 0;
        return entry.TryGetProperty(name, out var element) && element.ValueKind == JsonValueKind.Number &&
               element.TryGetInt32(out value);
    }
}
