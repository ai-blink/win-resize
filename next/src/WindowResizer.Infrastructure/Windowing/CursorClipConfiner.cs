using WindowResizer.Core.Windowing;
using static WindowResizer.Infrastructure.Windowing.NativeMethods;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>Core 의 <see cref="ICursorConfiner"/> 를 <see cref="CursorClip"/> 으로 잇는다. 실제 마우스 제한은 CursorClip 이 한다.</summary>
public sealed class CursorClipConfiner : ICursorConfiner
{
    public PixelRect? Current() => CursorClip.Current();
    public bool Confine(PixelRect rect) => CursorClip.Confine(rect);
    public bool Release() => CursorClip.Release();

    /// <summary>키가 지금 눌려 있는가(<c>GetAsyncKeyState</c> 의 최상위 비트).</summary>
    public static bool IsKeyDown(int virtualKey) => (GetAsyncKeyState(virtualKey) & 0x8000) != 0;

    public static nint Foreground() => GetForegroundWindow();
}
