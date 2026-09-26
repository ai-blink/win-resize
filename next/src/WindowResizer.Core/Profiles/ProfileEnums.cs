namespace WindowResizer.Core.Profiles;

/// <summary>
/// 프로필이 창을 찾는 방법. 저장 값은 snake_case 문자열이다(<c>exact_title</c> 등).
/// Python <c>MatchingStrategy</c> 와 값이 1:1 로 같아야 한다 - 이름을 바꾸면 기존 profiles.json 을 못 읽는다.
/// </summary>
public enum MatchingStrategy
{
    ExactTitle,
    TitleContains,
    TitleRegex,
    ProcessName,
    ExecutablePath,
    Combined,

    /// <summary>
    /// Python 쪽에 값만 정의돼 있고 매칭 구현이 없다(항상 불일치). 이 값을 가진 파일을
    /// 읽을 수는 있어야 하므로 남겨 둔다.
    /// </summary>
    Smart,
}

/// <summary>프로필 종류. 저장 값은 <c>window_config</c> / <c>layout</c> / <c>application</c> / <c>workspace</c>.</summary>
public enum ProfileType
{
    WindowConfig,
    Layout,
    Application,
    Workspace,
}
