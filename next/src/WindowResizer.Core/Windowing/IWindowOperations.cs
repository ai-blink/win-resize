namespace WindowResizer.Core.Windowing;

/// <summary>
/// 화면 위의 사각형. 단위는 <see cref="Profiles.WindowConfiguration"/> 과 같은 Win32 물리 픽셀,
/// 가상 데스크톱 좌표다.
/// </summary>
public readonly record struct PixelRect(int X, int Y, int Width, int Height)
{
    public int Right => X + Width;
    public int Bottom => Y + Height;
}

/// <summary>
/// 창이 최대화/최소화돼 있어도 남아 있는 "일반" 위치. <see cref="NormalRect"/> 는 화면 좌표로 바꾼 값이다.
/// <see cref="RestoresToMaximized"/> 는 최소화된 창이 복원되면 최대화로 돌아가는가다.
/// </summary>
public readonly record struct WindowPlacement(PixelRect NormalRect, bool RestoresToMaximized);

/// <summary>
/// Core 가 창을 다루기 위해 필요한 것. 구현은 Infrastructure 의 Win32 어댑터다.
/// 창 핸들은 <see cref="nint"/> 로만 다룬다 - Core 는 그것이 HWND 라는 것 말고는 모른다.
///
/// 상태를 바꾸는 메서드의 반환값은 "호출이 성공을 돌려줬다"가 아니라
/// <b>호출 뒤 창이 실제로 그 상태인가</b>다.
/// </summary>
public interface IWindowOperations
{
    bool IsWindow(nint window);
    bool IsMaximized(nint window);
    bool IsMinimized(nint window);
    PixelRect? GetRect(nint window);
    WindowPlacement? GetPlacement(nint window);

    bool Restore(nint window);
    bool Maximize(nint window);
    bool Minimize(nint window);
    bool Move(nint window, PixelRect rect);
    bool SetTopmost(nint window, bool topmost);
}
