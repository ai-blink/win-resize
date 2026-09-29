using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Overlay;

/// <summary>오버레이 버튼과 스위치를 어디에 둘지. 좌표는 물리 픽셀 화면 좌표다.</summary>
public static class OverlayPlacement
{
    /// <summary>
    /// 새 버튼의 자리(PyQt5 <c>_next_overlay_position</c>): 주 모니터 작업 영역 오른쪽 아래에서 위로 계단식.
    /// 오른쪽에서 40, 아래에서 80 띄우고 버튼마다 높이+10 씩 올린다. 위로 넘치면 다시 아래에서 시작한다.
    /// </summary>
    public static ScreenPoint NextButton(PixelRect workArea, int width, int height, int index)
    {
        var x = workArea.Right - width - 40;
        var y = workArea.Bottom - height - 80 - index * (height + 10);
        if (y < workArea.Y) y = workArea.Bottom - height - 80;
        return new ScreenPoint(x, y);
    }

    /// <summary>스위치의 기본 자리(PyQt5 <c>_default_toggle_position</c>): 오른쪽 아래, 40/30 안쪽.</summary>
    public static ScreenPoint DefaultToggle(PixelRect workArea, int width, int height) =>
        new(workArea.Right - width - 40, workArea.Bottom - height - 30);

    /// <summary>
    /// 저장된 자리가 지금 모니터 중 하나에 충분히 걸쳐 있는가. 모니터를 뺐거나 배율이 바뀌면 화면 밖에 남은
    /// 버튼을 잡을 수 없다 - 그럴 땐 기본 자리로 되돌린다. 버튼의 가운데가 어느 모니터 안에 있으면 보인다고 본다.
    /// </summary>
    public static bool IsVisibleOn(ScreenPoint topLeft, int width, int height, IEnumerable<PixelRect> monitors)
    {
        var cx = topLeft.X + width / 2;
        var cy = topLeft.Y + height / 2;
        return monitors.Any(m => cx >= m.X && cx < m.Right && cy >= m.Y && cy < m.Bottom);
    }
}
