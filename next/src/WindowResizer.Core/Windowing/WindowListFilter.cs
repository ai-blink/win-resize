using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Windowing;

/// <summary>
/// 창 목록에 보여 줄 "사용자 창" 판정. PyQt5 <c>WindowEnumerator._apply_filter(USER_WINDOWS)</c> 와
/// <c>_is_system_window</c> 를 옮겼다. 보이는지는 열거 단계에서 이미 걸렀다고 본다.
/// </summary>
public static class WindowListFilter
{
    /// <summary>PyQt5 목록 그대로(소문자, 정확히 일치). <c>msaskswwclass</c> 오타도 원본 그대로 둔다 -
    /// 고치면 목록 동등성이 깨진다. 실제 작업 표시줄 클래스는 <c>MSTaskSwWClass</c> 라 이 항목은 원래 안 맞는다.</summary>
    private static readonly HashSet<string> SystemClasses = new(StringComparer.Ordinal)
    {
        "shell_traywnd", "workerw", "progman", "shell_secondarytraywnd",
        "notifyiconoverflowwindow", "tasklistthumbnailwnd", "msaskswwclass",
        "button", "tooltips_class32", "msctfime ui",
    };

    private static readonly HashSet<string> SystemTitles = new(StringComparer.Ordinal)
    {
        "", "program manager", "desktop",
    };

    public static bool IsUserWindow(WindowInfo window, PixelRect rect)
    {
        var title = window.Title ?? "";
        if (title.Trim().Length == 0) return false;
        if (SystemClasses.Contains((window.ClassName ?? "").ToLowerInvariant())) return false;
        if (SystemTitles.Contains(title.ToLowerInvariant())) return false;
        return rect.Width != 0 && rect.Height != 0;
    }
}
