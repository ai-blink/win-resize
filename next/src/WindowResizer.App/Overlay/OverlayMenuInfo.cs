using WindowResizer.Core.Overlay;

namespace WindowResizer.App.Overlay;

/// <summary>
/// 오버레이 버튼 우클릭 메뉴의 정보 줄: 이 버튼이 복원할 위치와 크기(D-032). 화면 요소를 만들지 않아 문자열만 검사할 수 있다.
/// </summary>
public static class OverlayMenuInfo
{
    public static string Position(OverlayButton button, Func<string, string> text) =>
        button.HasPlace
            ? string.Format(text("Overlay.Menu.Position"), button.X, button.Y, button.Width, button.Height)
              + (button.IsMaximized ? " " + text("Status.MaximizedMark") : "")
            : text("Overlay.Menu.NoPosition");
}
