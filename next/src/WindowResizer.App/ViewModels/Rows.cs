using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.App.ViewModels;

/// <summary>창 목록 한 줄. 열 구성은 PyQt5 와 같다: 창 이름, PID, 프로세스, X, Y, 폭, 높이.</summary>
public sealed record WindowRow(
    nint Handle,
    WindowInfo Info,
    uint ProcessId,
    PixelRect Rect,
    bool IsMaximized,
    bool IsMinimized)
{
    /// <summary>제목 뒤에 상태 표시를 붙인다(PyQt5 의 [MIN], [MAX] 와 같다).</summary>
    public string DisplayTitle =>
        IsMinimized ? Info.Title + " [MIN]" : IsMaximized ? Info.Title + " [MAX]" : Info.Title;

    public string ProcessName => Info.ProcessName;
}

/// <summary>
/// 프로필 목록 한 줄. 열 구성은 PyQt5 와 같다:
/// 프로필명, 대상창/프로세스, 단축키, 마우스 가둠, X, Y, 폭, 높이, 자동적용.
/// 예/아니오 같은 표시 문자열은 뷰가 리소스로 정한다 - 여기서는 값만 준다.
/// </summary>
public sealed record ProfileRow(string Id, Profile Profile)
{
    public string Name => Profile.Name;

    /// <summary>제목 패턴 -> 프로세스 패턴 -> 실행 파일 이름 순. 셋 다 없으면 빈 문자열(뷰가 "모든 창"으로 표시).</summary>
    public string Target
    {
        get
        {
            var c = Profile.MatchingCriteria;
            if (c is null) return "";
            if (!string.IsNullOrEmpty(c.WindowTitlePattern)) return c.WindowTitlePattern;
            if (!string.IsNullOrEmpty(c.ProcessNamePattern)) return c.ProcessNamePattern;
            return string.IsNullOrEmpty(c.ExecutablePathPattern) ? "" : System.IO.Path.GetFileName(c.ExecutablePathPattern);
        }
    }

    public string? TargetTooltip => Profile.MatchingCriteria?.ExecutablePathPattern;

    public string Hotkey =>
        Profile.HotkeyEnabled && !string.IsNullOrEmpty(Profile.HotkeyCombination) ? Profile.HotkeyCombination : "-";

    public bool MouseConstraint => Profile.MouseConstraint;
    public bool AutoApply => Profile.AutoApply;

    public string X => Profile.WindowConfig?.X.ToString() ?? "-";
    public string Y => Profile.WindowConfig?.Y.ToString() ?? "-";
    public string Width => Profile.WindowConfig?.Width.ToString() ?? "-";
    public string Height => Profile.WindowConfig?.Height.ToString() ?? "-";
}
