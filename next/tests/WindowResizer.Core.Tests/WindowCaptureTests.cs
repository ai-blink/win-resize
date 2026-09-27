using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

/// <summary>캡처 규칙(D-021). 상태별로 어느 사각형을 뜨는지 가짜 창으로 잰다.</summary>
[TestClass]
public sealed class WindowCaptureTests
{
    private static readonly nint Target = 7;
    private static readonly PixelRect Normal = new(100, 80, 900, 600);

    [TestMethod]
    public void Normal_window_is_captured_from_its_current_rectangle()
    {
        var windows = new FakeWindows { Rect = new PixelRect(10, 20, 640, 480), Placement = new(Normal, false) };

        var result = WindowCapture.Capture(windows, Target);

        Assert.AreEqual(CaptureRefusal.None, result.Refusal);
        Assert.AreEqual((10, 20, 640, 480, false),
            (result.Configuration!.X, result.Configuration.Y, result.Configuration.Width, result.Configuration.Height, result.Configuration.IsMaximized));
    }

    [TestMethod]
    public void Maximized_window_keeps_its_normal_placement_and_the_flag()
    {
        var windows = new FakeWindows { Maximized = true, Rect = new PixelRect(-8, -8, 1936, 1048), Placement = new(Normal, false) };

        var config = WindowCapture.Capture(windows, Target).Configuration!;

        Assert.AreEqual(Normal, new PixelRect(config.X, config.Y, config.Width, config.Height));
        Assert.IsTrue(config.IsMaximized);
        Assert.IsFalse(config.IsMinimized);
    }

    [TestMethod]
    public void Minimized_window_uses_normal_placement_not_the_minus_32000_rectangle()
    {
        var windows = new FakeWindows { Minimized = true, Rect = new PixelRect(-32000, -32000, 160, 28), Placement = new(Normal, true) };

        var config = WindowCapture.Capture(windows, Target).Configuration!;

        Assert.AreEqual(Normal, new PixelRect(config.X, config.Y, config.Width, config.Height));
        Assert.IsTrue(config.IsMaximized, "복원하면 최대화로 돌아가는 창");
        Assert.IsFalse(config.IsMinimized, "적용할 때마다 창을 내리는 프로필은 만들지 않는다");
    }

    [TestMethod]
    public void Unplaceable_or_missing_windows_are_refused_with_a_reason()
    {
        var sentinel = new FakeWindows { Minimized = true, Placement = new(new PixelRect(-32000, -32000, 160, 28), false) };
        Assert.AreEqual(CaptureRefusal.Unplaceable, WindowCapture.Capture(sentinel, Target).Refusal);

        var empty = new FakeWindows { Rect = new PixelRect(0, 0, 0, 0) };
        Assert.AreEqual(CaptureRefusal.Unplaceable, WindowCapture.Capture(empty, Target).Refusal);

        var noPlacement = new FakeWindows { Maximized = true, Placement = null };
        Assert.AreEqual(CaptureRefusal.NoPlacement, WindowCapture.Capture(noPlacement, Target).Refusal);

        var gone = new FakeWindows { Exists = false };
        var result = WindowCapture.Capture(gone, Target);
        Assert.AreEqual(CaptureRefusal.WindowGone, result.Refusal);
        Assert.IsFalse(result.Succeeded);
    }

    private sealed class FakeWindows : IWindowOperations
    {
        public bool Exists { get; set; } = true;
        public bool Maximized { get; set; }
        public bool Minimized { get; set; }
        public PixelRect? Rect { get; set; }
        public WindowPlacement? Placement { get; set; }

        public bool IsWindow(nint window) => Exists;
        public bool IsMaximized(nint window) => Maximized;
        public bool IsMinimized(nint window) => Minimized;
        public PixelRect? GetRect(nint window) => Rect;
        public WindowPlacement? GetPlacement(nint window) => Placement;

        public bool Restore(nint window) => throw new InvalidOperationException("캡처는 창을 바꾸지 않는다");
        public bool Maximize(nint window) => throw new InvalidOperationException("캡처는 창을 바꾸지 않는다");
        public bool Minimize(nint window) => throw new InvalidOperationException("캡처는 창을 바꾸지 않는다");
        public bool Move(nint window, PixelRect rect) => throw new InvalidOperationException("캡처는 창을 바꾸지 않는다");
        public bool SetTopmost(nint window, bool topmost) => throw new InvalidOperationException("캡처는 창을 바꾸지 않는다");
    }
}
