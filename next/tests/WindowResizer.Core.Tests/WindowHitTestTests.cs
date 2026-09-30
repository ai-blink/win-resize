using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

[TestClass]
public sealed class WindowHitTestTests
{
    private sealed record W(string Name, PixelRect Rect, bool Skip = false);

    private static string? At(W[] windows, int x, int y) =>
        WindowHitTest.TopmostAt(windows, w => w.Rect, w => w.Skip, x, y)?.Name;

    [TestMethod]
    public void The_first_window_in_z_order_that_contains_the_point_wins()
    {
        var windows = new[]
        {
            new W("front", new PixelRect(100, 100, 200, 200)),
            new W("back", new PixelRect(0, 0, 500, 500)),
        };

        Assert.AreEqual("front", At(windows, 150, 150));
        Assert.AreEqual("back", At(windows, 400, 400), "앞 창 밖의 점은 뒤 창이 받는다");
        Assert.IsNull(At(windows, 600, 600));
    }

    [TestMethod]
    public void Skipped_windows_and_empty_rects_are_passed_through()
    {
        var windows = new[]
        {
            new W("own", new PixelRect(0, 0, 500, 500), Skip: true),
            new W("empty", new PixelRect(10, 10, 0, 0)),
            new W("real", new PixelRect(0, 0, 300, 300)),
        };

        Assert.AreEqual("real", At(windows, 20, 20));
    }

    [TestMethod]
    public void A_shared_edge_belongs_to_the_window_on_the_right_and_below()
    {
        var windows = new[]
        {
            new W("left", new PixelRect(0, 0, 100, 100)),
            new W("right", new PixelRect(100, 0, 100, 100)),
        };

        Assert.AreEqual("left", At(windows, 99, 50));
        Assert.AreEqual("right", At(windows, 100, 50));
    }

    [TestMethod]
    public void Windows_on_a_monitor_left_of_the_primary_are_found_with_negative_coordinates()
    {
        var windows = new[] { new W("left-monitor", new PixelRect(-1920, 0, 1920, 1080)) };
        Assert.AreEqual("left-monitor", At(windows, -100, 500));
        Assert.IsNull(At(windows, 0, 500));
    }
}
