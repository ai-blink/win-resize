namespace WindowResizer.Core.Overlay;

public enum GestureRelease
{
    None,
    /// <summary>움직임이 문턱보다 작았다. 클릭 모드면 발동한다.</summary>
    Click,
    /// <summary>드래그로 옮겼다. 자리를 저장할 때다.</summary>
    DragEnded,
}

/// <summary>
/// 오버레이 버튼 하나의 마우스 규칙(PyQt5 <c>OverlayButton</c> 의 mouse*/dwell 메서드). WPF 없이 테스트하려고
/// 창에서 떼어 냈다. 좌표는 물리 픽셀 화면 좌표다.
///
/// - 누른 뒤 맨해튼 거리 5px 미만으로 움직였으면 클릭, 그 이상이면 드래그다. 잠겨 있으면 드래그하지 않는다.
/// - 드웰은 들어오면 차기 시작하고, 나가면 취소되며 다시 장전된다. 한 번 머무름에 한 번만 발동한다.
/// - 누르면(배치하려는 것이므로) 드웰을 멈춘다.
/// </summary>
public sealed class OverlayGesture
{
    public const int DragThresholdPx = 5;

    private ScreenPoint? _pressCursor;
    private ScreenPoint _pressWindow;
    private bool _dragged;
    private bool _dwelling;
    private bool _armed = true;
    private double _elapsedMs;

    public bool Locked { get; set; }

    public bool Hovered { get; private set; }

    public void Press(ScreenPoint cursor, ScreenPoint windowTopLeft)
    {
        CancelDwell();
        _pressCursor = cursor;
        _pressWindow = windowTopLeft;
        _dragged = false;
    }

    /// <summary>창을 옮길 새 왼쪽 위. 옮기지 않을 때는 null.</summary>
    public ScreenPoint? Move(ScreenPoint cursor)
    {
        if (Locked || _pressCursor is not { } press) return null;

        var dx = cursor.X - press.X;
        var dy = cursor.Y - press.Y;
        if (!_dragged && Math.Abs(dx) + Math.Abs(dy) < DragThresholdPx) return null;

        _dragged = true;
        return new ScreenPoint(_pressWindow.X + dx, _pressWindow.Y + dy);
    }

    /// <param name="dwellMode">지금 발동 방식이 드웰인가. 드래그를 마치면 마우스가 아직 위에 있으니 다시 채운다.</param>
    public GestureRelease Release(bool dwellMode)
    {
        if (_pressCursor is null) return GestureRelease.None;

        var wasDrag = _dragged;
        _pressCursor = null;
        _dragged = false;

        if (!wasDrag) return GestureRelease.Click;
        if (dwellMode && Hovered && _armed) StartDwell();
        return GestureRelease.DragEnded;
    }

    public void Enter(bool dwellMode)
    {
        Hovered = true;
        if (dwellMode && _armed) StartDwell();
    }

    public void Leave()
    {
        Hovered = false;
        CancelDwell();
        _armed = true;
    }

    /// <summary>시간이 흘렀다. 드웰이 다 찼으면 true(한 번만) - 나갔다 들어오기 전까지 다시 발동하지 않는다.</summary>
    public bool Tick(double elapsedMs, int dwellMs)
    {
        if (!_dwelling) return false;
        _elapsedMs += elapsedMs;
        if (_elapsedMs < dwellMs) return false;

        _dwelling = false;
        _elapsedMs = 0;
        _armed = false;
        return true;
    }

    public bool IsDwelling => _dwelling;

    /// <summary>0-1 드웰 진행률. 게이지가 그린다.</summary>
    public double Progress(int dwellMs) => _dwelling && dwellMs > 0 ? Math.Min(1.0, _elapsedMs / dwellMs) : 0.0;

    /// <summary>발동 방식이나 시간이 바뀌었다. 차던 것을 버린다.</summary>
    public void CancelDwell()
    {
        _dwelling = false;
        _elapsedMs = 0;
    }

    private void StartDwell()
    {
        _dwelling = true;
        _elapsedMs = 0;
    }
}
