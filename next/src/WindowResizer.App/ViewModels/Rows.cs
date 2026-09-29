using WindowResizer.Core.Hotkeys;
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
/// <param name="IsUnreadable">
/// 파일에 있지만 읽지 못한 프로필(D-022). 흐리게 보이고 삭제만 된다. <see cref="Profile"/> 은 이름만 채운 자리표시다.
/// </param>
public sealed record ProfileRow(string Id, Profile Profile, bool IsUnreadable = false, string? Error = null)
{
    public static ProfileRow ForUnreadable(UnreadableProfile u) =>
        new(u.Id, new Profile { Name = u.DisplayName }, IsUnreadable: true, Error: u.Error);

    public string Name => Profile.Name;

    /// <summary>제목 패턴 -> 프로세스 패턴 -> 실행 파일 이름 순. 셋 다 없으면 빈 문자열(뷰가 "모든 창"으로 표시).</summary>
    public string Target
    {
        get
        {
            if (IsUnreadable) return "-";
            var c = Profile.MatchingCriteria;
            if (c is null) return "";
            if (!string.IsNullOrEmpty(c.WindowTitlePattern)) return c.WindowTitlePattern;
            if (!string.IsNullOrEmpty(c.ProcessNamePattern)) return c.ProcessNamePattern;
            return string.IsNullOrEmpty(c.ExecutablePathPattern) ? "" : System.IO.Path.GetFileName(c.ExecutablePathPattern);
        }
    }

    public string? TargetTooltip => Profile.MatchingCriteria?.ExecutablePathPattern;

    /// <summary>등록되는 첫 단축키(세트가 있으면 세트의 첫 항목). 없으면 "-".</summary>
    public string Hotkey => !Profile.HotkeyEnabled
        ? "-"
        : HotkeyPlanner.EffectiveSets(Profile).FirstOrDefault(s => s.Enabled && !string.IsNullOrWhiteSpace(s.Combination))
            ?.Combination ?? "-";

    public bool MouseConstraint => Profile.MouseConstraint;

    /// <summary>이 프로필의 오버레이 버튼을 띄우는가. 읽지 못한 프로필은 띄우지 않는다.</summary>
    public bool OverlayEnabled => !IsUnreadable && Profile.OverlayStyle?.Enabled == true;
    public bool AutoApply => Profile.AutoApply;

    public string X => Profile.WindowConfig?.X.ToString() ?? "-";
    public string Y => Profile.WindowConfig?.Y.ToString() ?? "-";
    public string Width => Profile.WindowConfig?.Width.ToString() ?? "-";
    public string Height => Profile.WindowConfig?.Height.ToString() ?? "-";
}
