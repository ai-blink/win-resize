using WindowResizer.Core.Profiles;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 오버레이 버튼 우클릭 메뉴의 정보 줄: 이 버튼이 어느 프로필의 무엇에 연결됐는지. 첫 묶음은 연결 대상(매칭 방식과
/// 값), 둘째 묶음은 저장된 위치와 크기다. 화면 요소를 만들지 않아 문자열만 검사할 수 있다.
/// </summary>
public static class OverlayMenuInfo
{
    public sealed record Lines(IReadOnlyList<string> Target, string Position);

    public static Lines Describe(Profile profile, Func<string, string> text)
    {
        return new Lines(Target(profile.MatchingCriteria, text), Position(profile.WindowConfig, text));
    }

    private static IReadOnlyList<string> Target(MatchingCriteria? m, Func<string, string> text)
    {
        if (m is null) return [text("Overlay.Menu.Empty")];

        var label = m.Strategy == MatchingStrategy.Smart ? nameof(MatchingStrategy.Smart) : text("Strategy." + m.Strategy);
        string Or(string? value) => string.IsNullOrEmpty(value) ? text("Overlay.Menu.Empty") : value;

        switch (m.Strategy)
        {
            case MatchingStrategy.ExecutablePath:
                var path = m.ExecutablePathPattern;
                var file = string.IsNullOrEmpty(path) ? "" : System.IO.Path.GetFileName(path.Replace('/', '\\'));
                return string.IsNullOrEmpty(file) ? [label, Or(path)] : [$"{file} ({label})", Or(path)];
            case MatchingStrategy.ProcessName:
                return [label, Or(m.ProcessNamePattern)];
            case MatchingStrategy.Combined:
            {
                var lines = new List<string> { label };
                if (!string.IsNullOrEmpty(m.WindowTitlePattern)) lines.Add(string.Format(text("Overlay.Menu.Title"), m.WindowTitlePattern));
                if (!string.IsNullOrEmpty(m.ProcessNamePattern)) lines.Add(string.Format(text("Overlay.Menu.Process"), m.ProcessNamePattern));
                if (!string.IsNullOrEmpty(m.WindowClassPattern)) lines.Add(string.Format(text("Overlay.Menu.Class"), m.WindowClassPattern));
                if (!string.IsNullOrEmpty(m.ExecutablePathPattern)) lines.Add(string.Format(text("Overlay.Menu.Path"), m.ExecutablePathPattern));
                return lines;
            }
            case MatchingStrategy.Smart:
                return [label];
            default:
                return [label, Or(m.WindowTitlePattern)];
        }
    }

    private static string Position(WindowConfiguration? c, Func<string, string> text) =>
        c is null
            ? text("Overlay.Menu.NoPosition")
            : string.Format(text("Overlay.Menu.Position"), c.X, c.Y, c.Width, c.Height)
              + (c.IsMaximized ? " " + text("Status.MaximizedMark") : "");
}
