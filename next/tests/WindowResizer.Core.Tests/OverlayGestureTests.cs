using WindowResizer.Core.Overlay;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

/// <summary>오버레이 버튼의 마우스 규칙과 자리 규칙(PyQt5 overlay_button.py, main_window.py 와 같다).</summary>
[TestClass]
public sealed class OverlayGestureTests
{
    private static readonly ScreenPoint Window = new(1000, 800);

    [TestMethod]
    public void Small_movement_is_a_click_and_five_pixels_start_a_drag()
    {
        var g = new OverlayGesture();

        g.Press(new ScreenPoint(10, 10), Window);
        Assert.IsNull(g.Move(new ScreenPoint(12, 12)), "맨해튼 4px 은 아직 클릭이다");
        Assert.AreEqual(GestureRelease.Click, g.Release(dwellMode: false));

        g.Press(new ScreenPoint(10, 10), Window);
        Assert.AreEqual(new ScreenPoint(1003, 802), g.Move(new ScreenPoint(13, 12)), "5px 부터 드래그, 창은 커서만큼 간다");
        Assert.AreEqual(new ScreenPoint(1001, 801), g.Move(new ScreenPoint(11, 11)), "드래그가 시작되면 문턱 아래로 돌아와도 따라간다");
        Assert.AreEqual(GestureRelease.DragEnded, g.Release(dwellMode: false));
        Assert.AreEqual(GestureRelease.None, g.Release(dwellMode: false), "누르지 않은 놓기는 아무것도 아니다");
    }

    [TestMethod]
    public void Locked_buttons_do_not_move_and_still_click()
    {
        var g = new OverlayGesture { Locked = true };

        g.Press(new ScreenPoint(0, 0), Window);
        Assert.IsNull(g.Move(new ScreenPoint(200, 200)));
        Assert.AreEqual(GestureRelease.Click, g.Release(dwellMode: false));
    }

    [TestMethod]
    public void Dwell_fires_once_per_hover_and_rearms_after_leaving()
    {
        var g = new OverlayGesture();

        g.Enter(dwellMode: true);
        Assert.IsFalse(g.Tick(500, 800));
        Assert.AreEqual(0.625, g.Progress(800), 1e-9);
        Assert.IsTrue(g.Tick(300, 800), "800ms 가 차면 발동");
        Assert.IsFalse(g.IsDwelling);
        Assert.IsFalse(g.Tick(5000, 800), "나갔다 들어오기 전까지 다시 발동하지 않는다");

        g.Leave();
        g.Enter(dwellMode: true);
        Assert.IsTrue(g.IsDwelling);
        Assert.IsTrue(g.Tick(800, 800));
    }

    [TestMethod]
    public void Click_mode_never_dwells_and_leaving_cancels_the_fill()
    {
        var g = new OverlayGesture();
        g.Enter(dwellMode: false);
        Assert.IsFalse(g.IsDwelling);

        g.Leave();
        g.Enter(dwellMode: true);
        g.Tick(700, 800);
        g.Leave();
        Assert.AreEqual(0.0, g.Progress(800));
    }

    [TestMethod]
    public void Pressing_stops_the_dwell_and_finishing_a_drag_refills_it_while_hovered()
    {
        var g = new OverlayGesture();
        g.Enter(dwellMode: true);
        g.Tick(700, 800);

        g.Press(new ScreenPoint(0, 0), Window);
        Assert.IsFalse(g.IsDwelling, "배치하려고 누른 것이므로 드웰을 멈춘다");

        g.Move(new ScreenPoint(30, 0));
        g.Release(dwellMode: true);
        Assert.IsTrue(g.IsDwelling);
        Assert.AreEqual(0.0, g.Progress(800), "처음부터 다시 찬다");
    }

    [TestMethod]
    public void New_buttons_stack_upward_from_the_bottom_right_and_wrap()
    {
        var work = new PixelRect(0, 0, 1920, 1040);

        Assert.AreEqual(new ScreenPoint(1920 - 150 - 40, 1040 - 46 - 80), OverlayPlacement.NextButton(work, 150, 46, 0));
        Assert.AreEqual(new ScreenPoint(1730, 914 - 56), OverlayPlacement.NextButton(work, 150, 46, 1));
        Assert.AreEqual(new ScreenPoint(1730, 914), OverlayPlacement.NextButton(work, 150, 46, 100), "위로 넘치면 아래에서 다시");
    }

    [TestMethod]
    public void A_saved_spot_counts_only_while_its_centre_is_on_a_monitor()
    {
        var monitors = new[] { new PixelRect(-1920, 0, 1920, 1080), new PixelRect(0, 0, 3840, 2160) };

        Assert.IsTrue(OverlayPlacement.IsVisibleOn(new ScreenPoint(-500, 200), 150, 46, monitors), "왼쪽 보조 모니터");
        Assert.IsFalse(OverlayPlacement.IsVisibleOn(new ScreenPoint(5000, 200), 150, 46, monitors), "뺀 모니터 자리");
        Assert.IsFalse(OverlayPlacement.IsVisibleOn(new ScreenPoint(-2100, 200), 150, 46, monitors));
    }
}
