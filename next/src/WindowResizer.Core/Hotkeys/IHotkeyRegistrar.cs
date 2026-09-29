namespace WindowResizer.Core.Hotkeys;

/// <summary>등록 시도 하나의 결과. 성공하면 <see cref="ErrorCode"/> 는 0.</summary>
public sealed record HotkeyRegistration(HotkeyBinding Binding, bool Registered, int ErrorCode);

/// <summary>
/// 전역 단축키를 등록하는 쪽(Infrastructure <c>HotkeyRegistrar</c>). 등록은 통째로 바꾼다 - 프로필을 저장하거나
/// 지울 때마다 PyQt5 처럼 전부 지우고 다시 등록한다.
/// </summary>
public interface IHotkeyRegistrar
{
    /// <summary>등록한 단축키가 눌렸다. <b>등록기의 전용 스레드에서</b> 불리므로 받는 쪽이 UI 스레드로 넘긴다.</summary>
    event Action<HotkeyBinding>? Activated;

    /// <summary>등록을 전부 지우고 주어진 것을 등록한다. 하나가 실패해도 나머지는 등록한다.</summary>
    IReadOnlyList<HotkeyRegistration> Replace(IReadOnlyList<HotkeyBinding> bindings);
}
