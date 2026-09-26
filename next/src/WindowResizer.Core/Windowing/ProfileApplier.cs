using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Windowing;

public enum ApplyOutcome
{
    Applied,
    InvalidConfiguration,
    WindowGone,
    RestoreFailed,
    MoveFailed,
}

/// <summary>
/// 프로필의 위치와 크기를 창에 적용한다. 순서는 PyQt5 <c>Profile.apply_to_window</c> 와 같다.
///
/// 1. 프로필이 최대화를 원하지 않는데 창이 최대화돼 있으면 <b>먼저 복원</b>한다. 최대화된 창은
///    저장된 일반 크기를 무시하므로, 그대로 옮기면 좌표가 먹지 않는다. 복원이 실패하면 멈춘다.
/// 2. 위치와 크기를 적용한다.
/// 3. 프로필이 최대화/최소화 상태면 그 상태로 바꾼다.
/// 4. 항상 위를 켜거나 끈다(끄는 것도 적용이다).
///
/// 위치 잠금, 마우스 제한, 자동 복원 감시는 이 클래스의 일이 아니다(S3c 이후).
/// </summary>
public sealed class ProfileApplier(IWindowOperations windows)
{
    public ApplyOutcome Apply(nint window, WindowConfiguration config)
    {
        if (!config.IsValid()) return ApplyOutcome.InvalidConfiguration;
        if (!windows.IsWindow(window)) return ApplyOutcome.WindowGone;

        if (!config.IsMaximized && windows.IsMaximized(window) && !windows.Restore(window))
            return ApplyOutcome.RestoreFailed;

        if (!windows.Move(window, new PixelRect(config.X, config.Y, config.Width, config.Height)))
            return ApplyOutcome.MoveFailed;

        if (config.IsMaximized) windows.Maximize(window);
        else if (config.IsMinimized) windows.Minimize(window);

        windows.SetTopmost(window, config.AlwaysOnTop);
        return ApplyOutcome.Applied;
    }
}
