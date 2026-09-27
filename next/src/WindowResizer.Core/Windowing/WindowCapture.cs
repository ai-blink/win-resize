using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Windowing;

public enum CaptureRefusal
{
    None,
    WindowGone,
    NoPlacement,
    /// <summary>화면에 둘 수 없는 사각형 - 최소화된 창의 -32000 좌표나 크기 0.</summary>
    Unplaceable,
}

public sealed record CaptureResult(WindowConfiguration? Configuration, CaptureRefusal Refusal)
{
    public bool Succeeded => Configuration is not null;
}

/// <summary>
/// 지금 창의 위치와 상태를 프로필 설정으로 뜬다(D-021). 새 프로필, 위치 덮어쓰기, 편집 창의
/// "현재 창에서 가져오기" 세 경로가 모두 이 규칙 하나를 쓴다.
///
/// - 일반 상태: 지금 사각형. 스냅된 창은 일반 위치가 스냅 전 값이라 지금 사각형이 맞다.
/// - 최대화: 일반 위치 + <c>IsMaximized</c>. 최대화 사각형을 저장하면 복원 크기를 잃는다.
/// - 최소화: 일반 위치 + 복원되면 최대화인지. <c>IsMinimized</c> 는 뜨지 않는다 - 적용할 때마다
///   창을 내려 버리는 프로필은 사용자가 원한 것이 아니다.
/// - 어느 경로든 결과가 화면에 둘 수 없는 사각형이면 거절하고 이유를 돌려준다.
/// </summary>
public static class WindowCapture
{
    /// <summary>Windows 가 최소화된 창을 옮겨 두는 좌표. 실제 가상 데스크톱은 여기까지 가지 않는다.</summary>
    private const int MinimizedSentinel = -32000;

    public static CaptureResult Capture(IWindowOperations windows, nint window)
    {
        if (!windows.IsWindow(window)) return Refuse(CaptureRefusal.WindowGone);

        PixelRect? rect;
        var maximized = false;
        if (windows.IsMaximized(window) || windows.IsMinimized(window))
        {
            var placement = windows.GetPlacement(window);
            if (placement is null) return Refuse(CaptureRefusal.NoPlacement);
            rect = placement.Value.NormalRect;
            maximized = windows.IsMaximized(window) || placement.Value.RestoresToMaximized;
        }
        else
        {
            rect = windows.GetRect(window);
            if (rect is null) return Refuse(CaptureRefusal.NoPlacement);
        }

        var r = rect.Value;
        if (r.Width <= 0 || r.Height <= 0 || r.X <= MinimizedSentinel || r.Y <= MinimizedSentinel)
            return Refuse(CaptureRefusal.Unplaceable);

        return new CaptureResult(
            new WindowConfiguration { X = r.X, Y = r.Y, Width = r.Width, Height = r.Height, IsMaximized = maximized },
            CaptureRefusal.None);
    }

    private static CaptureResult Refuse(CaptureRefusal reason) => new(null, reason);
}
