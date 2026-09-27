using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

/// <summary>적용 순서. 순서 의존이라 실제 창 없이 기록용 가짜로 잰다.</summary>
[TestClass]
public sealed class ProfileApplierTests
{
    private static readonly nint Target = 42;

    // tests/test_profile_preview_and_auto_apply.py
    //   test_maximized_target_is_restored_before_normal_geometry_is_applied
    [TestMethod]
    public void Maximized_target_is_restored_before_normal_geometry_is_applied()
    {
        var windows = new RecordingWindows { Maximized = true };

        var outcome = new ProfileApplier(windows).Apply(Target, Config(30, 40, 500, 300));

        Assert.AreEqual(ApplyOutcome.Applied, outcome);
        CollectionAssert.AreEqual(
            new[] { "restore", "move 30,40 500x300", "topmost False" },
            windows.Calls);
    }

    [TestMethod]
    public void Normal_target_is_moved_without_a_restore()
    {
        var windows = new RecordingWindows();

        new ProfileApplier(windows).Apply(Target, Config(0, 0, 800, 600));

        CollectionAssert.AreEqual(new[] { "move 0,0 800x600", "topmost False" }, windows.Calls);
    }

    [TestMethod]
    public void Failed_restore_stops_before_moving()
    {
        var windows = new RecordingWindows { Maximized = true, RestoreSucceeds = false };

        var outcome = new ProfileApplier(windows).Apply(Target, Config(0, 0, 800, 600));

        Assert.AreEqual(ApplyOutcome.RestoreFailed, outcome);
        CollectionAssert.AreEqual(new[] { "restore" }, windows.Calls);
    }

    [TestMethod]
    public void Maximized_profile_is_moved_then_maximized_and_not_restored_first()
    {
        var windows = new RecordingWindows { Maximized = true };
        var config = Config(0, 0, 800, 600);
        config.IsMaximized = true;
        config.AlwaysOnTop = true;

        new ProfileApplier(windows).Apply(Target, config);

        CollectionAssert.AreEqual(new[] { "move 0,0 800x600", "maximize", "topmost True" }, windows.Calls);
    }

    [TestMethod]
    public void Invalid_configuration_or_missing_window_touches_nothing()
    {
        var windows = new RecordingWindows();

        Assert.AreEqual(ApplyOutcome.InvalidConfiguration, new ProfileApplier(windows).Apply(Target, Config(0, 0, 0, 600)));
        windows.Exists = false;
        Assert.AreEqual(ApplyOutcome.WindowGone, new ProfileApplier(windows).Apply(Target, Config(0, 0, 800, 600)));
        Assert.IsEmpty(windows.Calls);
    }

    private static WindowConfiguration Config(int x, int y, int w, int h) =>
        new() { X = x, Y = y, Width = w, Height = h };

    private sealed class RecordingWindows : IWindowOperations
    {
        public List<string> Calls { get; } = new();
        public bool Exists { get; set; } = true;
        public bool Maximized { get; set; }
        public bool RestoreSucceeds { get; set; } = true;

        public bool IsWindow(nint window) => Exists;
        public bool IsMaximized(nint window) => Maximized;
        public bool IsMinimized(nint window) => false;
        public PixelRect? GetRect(nint window) => null;
        public WindowPlacement? GetPlacement(nint window) => null;

        public bool Restore(nint window) { Calls.Add("restore"); return RestoreSucceeds; }
        public bool Maximize(nint window) { Calls.Add("maximize"); return true; }
        public bool Minimize(nint window) { Calls.Add("minimize"); return true; }
        public bool Move(nint window, PixelRect r) { Calls.Add($"move {r.X},{r.Y} {r.Width}x{r.Height}"); return true; }
        public bool SetTopmost(nint window, bool topmost) { Calls.Add($"topmost {topmost}"); return true; }
    }
}
