using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace WindowResizer.Core.Profiles;

/// <summary>매칭에 쓰는 창 정보. Infrastructure 가 Win32 에서 채운다.</summary>
public sealed record WindowInfo(
    string Title = "",
    string ProcessName = "",
    string ClassName = "",
    string ExecutablePath = "");

/// <summary>
/// 프로필을 창에 맞추는 조건. 판정 규칙은 Python <c>MatchingCriteria.matches_window</c> 를 그대로 옮겼다.
/// 잘못 옮기면 사용자가 쓰던 프로필이 조용히 안 맞는다.
/// </summary>
public sealed class MatchingCriteria
{
    [JsonPropertyName("strategy")] public MatchingStrategy Strategy { get; set; }
    [JsonPropertyName("window_title_pattern")] public string? WindowTitlePattern { get; set; }
    [JsonPropertyName("process_name_pattern")] public string? ProcessNamePattern { get; set; }
    [JsonPropertyName("window_class_pattern")] public string? WindowClassPattern { get; set; }
    [JsonPropertyName("executable_path_pattern")] public string? ExecutablePathPattern { get; set; }
    [JsonPropertyName("case_sensitive")] public bool CaseSensitive { get; set; }

    /// <summary>Python <c>re</c> 플래그 정수. <see cref="ToRegexOptions"/> 가 .NET 옵션으로 바꾼다.</summary>
    [JsonPropertyName("regex_flags")] public int RegexFlags { get; set; }

    /// <summary>클수록 우선.</summary>
    [JsonPropertyName("priority")] public int Priority { get; set; } = 50;

    [JsonPropertyName("auto_apply_enabled")] public bool AutoApplyEnabled { get; set; }

    /// <summary>창이 생긴 뒤 적용까지 기다리는 초.</summary>
    [JsonPropertyName("apply_delay")] public double ApplyDelay { get; set; } = 2.0;

    [JsonPropertyName("max_retries")] public int MaxRetries { get; set; } = 3;
    [JsonPropertyName("retry_delay")] public double RetryDelay { get; set; } = 0.5;
    [JsonPropertyName("only_on_startup")] public bool OnlyOnStartup { get; set; }

    public bool Matches(WindowInfo window)
    {
        try
        {
            return Strategy switch
            {
                MatchingStrategy.ExactTitle => MatchExactTitle(window),
                MatchingStrategy.TitleContains => MatchTitleContains(window),
                MatchingStrategy.TitleRegex => MatchTitleRegex(window),
                MatchingStrategy.ProcessName => MatchProcessName(window),
                MatchingStrategy.ExecutablePath => MatchExecutablePath(window),
                MatchingStrategy.Combined => MatchCombined(window),
                _ => false,
            };
        }
        catch (Exception)
        {
            return false;
        }
    }

    private StringComparison Comparison =>
        CaseSensitive ? StringComparison.Ordinal : StringComparison.OrdinalIgnoreCase;

    private bool MatchExactTitle(WindowInfo window) =>
        !string.IsNullOrEmpty(WindowTitlePattern) &&
        string.Equals(window.Title ?? "", WindowTitlePattern, Comparison);

    private bool MatchTitleContains(WindowInfo window) =>
        !string.IsNullOrEmpty(WindowTitlePattern) &&
        (window.Title ?? "").Contains(WindowTitlePattern, Comparison);

    private bool MatchTitleRegex(WindowInfo window)
    {
        if (string.IsNullOrEmpty(WindowTitlePattern)) return false;

        var options = ToRegexOptions(RegexFlags);
        if (!CaseSensitive) options |= RegexOptions.IgnoreCase;

        try
        {
            return Regex.IsMatch(
                window.Title ?? "", ToDotNetPattern(WindowTitlePattern), options, TimeSpan.FromMilliseconds(200));
        }
        catch (ArgumentException)
        {
            // Python 도 잘못된 정규식은 경고만 남기고 불일치로 본다.
            return false;
        }
    }

    /// <summary>Python 과 같다: 부분 일치다. <c>blender</c> 는 <c>blender.exe</c> 에 맞는다.</summary>
    private bool MatchProcessName(WindowInfo window) =>
        !string.IsNullOrEmpty(ProcessNamePattern) &&
        (window.ProcessName ?? "").Contains(ProcessNamePattern, Comparison);

    /// <summary>
    /// 실행 파일 전체 경로가 같아야 한다. hwnd 나 PID 가 아니라 경로로 찾으므로 프로세스를 다시 켜도 맞는다.
    /// 비교 전에 Python <c>os.path.normpath</c> (+ 대소문자 무시면 <c>normcase</c>) 와 같게 정규화한다.
    /// </summary>
    private bool MatchExecutablePath(WindowInfo window)
    {
        if (string.IsNullOrEmpty(ExecutablePathPattern)) return false;
        if (string.IsNullOrEmpty(window.ExecutablePath)) return false;

        return string.Equals(
            WindowsPath.Normalize(window.ExecutablePath),
            WindowsPath.Normalize(ExecutablePathPattern),
            Comparison);
    }

    /// <summary>채워진 조건을 전부 만족해야 한다(AND). 조건이 하나도 없으면 불일치.</summary>
    private bool MatchCombined(WindowInfo window)
    {
        var hasCriteria = false;

        if (!string.IsNullOrEmpty(WindowTitlePattern))
        {
            hasCriteria = true;
            if (!MatchTitleContains(window)) return false;
        }

        if (!string.IsNullOrEmpty(ProcessNamePattern))
        {
            hasCriteria = true;
            if (!MatchProcessName(window)) return false;
        }

        if (!string.IsNullOrEmpty(WindowClassPattern))
        {
            hasCriteria = true;
            if (!(window.ClassName ?? "").Contains(WindowClassPattern, Comparison)) return false;
        }

        if (!string.IsNullOrEmpty(ExecutablePathPattern))
        {
            hasCriteria = true;
            if (!MatchExecutablePath(window)) return false;
        }

        return hasCriteria;
    }

    /// <summary>
    /// Python <c>re</c> 플래그를 .NET 옵션으로 옮긴다.
    /// IGNORECASE=2, MULTILINE=8, DOTALL=16, VERBOSE=64. 나머지(LOCALE, ASCII 등)는 대응이 없어 버린다.
    /// </summary>
    public static RegexOptions ToRegexOptions(int pythonFlags)
    {
        var options = RegexOptions.None;
        if ((pythonFlags & 2) != 0) options |= RegexOptions.IgnoreCase;
        if ((pythonFlags & 8) != 0) options |= RegexOptions.Multiline;
        if ((pythonFlags & 16) != 0) options |= RegexOptions.Singleline;
        if ((pythonFlags & 64) != 0) options |= RegexOptions.IgnorePatternWhitespace;
        return options;
    }

    /// <summary>
    /// 두 문법이 갈리는 곳 중 제목 패턴에 나올 만한 이름 그룹만 바꾼다:
    /// <c>(?P&lt;name&gt;</c> 를 <c>(?&lt;name&gt;</c> 로, <c>(?P=name)</c> 를 <c>\k&lt;name&gt;</c> 로.
    /// </summary>
    private static string ToDotNetPattern(string pythonPattern) =>
        Regex.Replace(
            pythonPattern.Replace("(?P<", "(?<", StringComparison.Ordinal),
            @"\(\?P=(\w+)\)",
            @"\k<$1>");
}

/// <summary>Python <c>ntpath.normpath</c> 와 같은 규칙으로 Windows 경로를 정규화한다. 플랫폼 중립 코드다.</summary>
internal static class WindowsPath
{
    public static string Normalize(string path)
    {
        var p = path.Replace('/', '\\');

        // 드라이브("C:") 또는 UNC("\\server\share") 접두를 떼어 둔다.
        var prefix = "";
        if (p.StartsWith(@"\\", StringComparison.Ordinal))
        {
            var parts = p.Substring(2).Split('\\', 3);
            if (parts.Length >= 2)
            {
                prefix = @"\\" + parts[0] + @"\" + parts[1];
                p = parts.Length == 3 ? @"\" + parts[2] : "";
            }
        }
        else if (p.Length >= 2 && p[1] == ':')
        {
            prefix = p.Substring(0, 2);
            p = p.Substring(2);
        }

        var rooted = p.StartsWith('\\');
        var stack = new List<string>();
        foreach (var part in p.Split('\\'))
        {
            if (part.Length == 0 || part == ".") continue;
            if (part == ".." && stack.Count > 0 && stack[^1] != "..")
            {
                stack.RemoveAt(stack.Count - 1);
                continue;
            }
            if (part == ".." && rooted) continue;
            stack.Add(part);
        }

        var body = string.Join('\\', stack);
        var result = prefix + (rooted ? "\\" : "") + body;
        return result.Length == 0 ? "." : result;
    }
}
