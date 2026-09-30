namespace WindowResizer.Core.Windowing;

/// <summary>
/// 화면의 한 점 아래에서 <b>제일 위에 보이는 창</b>을 찾는다(화면에서 창 고르기, D-034).
/// 열거는 Z 순서 위에서 아래로 온다(Win32 <c>EnumWindows</c>) - 처음 걸리는 창이 사용자가 보는 창이다.
/// </summary>
public static class WindowHitTest
{
    /// <param name="orderedTopFirst">위에 있는 창부터.</param>
    /// <param name="rectOf">창의 화면 위치(물리 픽셀).</param>
    /// <param name="skip">고를 수 없는 창(이 앱의 창, 최소화된 창 등).</param>
    /// <returns>없으면 default.</returns>
    public static T? TopmostAt<T>(IEnumerable<T> orderedTopFirst, Func<T, PixelRect> rectOf, Func<T, bool> skip, int x, int y)
    {
        foreach (var window in orderedTopFirst)
        {
            if (skip(window)) continue;
            var r = rectOf(window);
            // 가장자리는 위/왼쪽만 포함한다 - 이웃한 창의 경계선 한 점이 두 창에 속하지 않게.
            if (r.Width > 0 && r.Height > 0 && x >= r.X && x < r.X + r.Width && y >= r.Y && y < r.Y + r.Height)
                return window;
        }
        return default;
    }
}
