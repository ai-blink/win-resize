namespace WindowResizer.Core.Windowing;

/// <summary>
/// 오버레이 버튼이 프로필을 적용할 "직전에 쓰던 창"이 될 수 있는가. PyQt5 <c>foreground_tracker.py</c> 의
/// <c>_is_trackable</c> 을 옮겼다. 바탕화면, 작업 표시줄 같은 셸 창이 잠깐 전경이 되어도 대상을 덮어쓰지 않는다.
/// 이 앱 자신의 창(본창, 오버레이 버튼)은 Infrastructure 가 프로세스 단위로 거른다.
/// </summary>
public static class ForegroundRules
{
    private static readonly HashSet<string> ShellClasses = new(StringComparer.Ordinal)
    {
        "Progman",
        "WorkerW",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "NotifyIconOverflowWindow",
        "Windows.UI.Core.CoreWindow",
        "TaskListThumbnailWnd",
        "ForegroundStaging",
    };

    public static bool IsTrackable(string className, bool isVisible) =>
        isVisible && !ShellClasses.Contains(className ?? "");
}
