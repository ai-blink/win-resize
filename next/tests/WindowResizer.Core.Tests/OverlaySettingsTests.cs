using WindowResizer.Core.Overlay;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

/// <summary>오버레이 전역 설정의 읽기 규칙(PyQt5 main_window.py 와 같다)과 왕복.</summary>
[TestClass]
public sealed class OverlaySettingsTests
{
    [TestMethod]
    public void Reads_the_values_pyqt5_actually_wrote()
    {
        // 2026-09-27 이 PC 의 HKCU\Software\WindowResizer\Overlay 값 그대로(DWORD 는 문자열로 읽힌다).
        var values = new Dictionary<string, string>
        {
            ["layout"] = """[{"profile_id": "7a6ee45390bffa0c", "x": 385, "y": 959}, {"profile_id": "dbc44eafbb44ea28", "x": 469, "y": 1010}]""",
            ["interaction_mode"] = "dwell",
            ["toggle_visible"] = "true",
            ["toggle_x"] = "254",
            ["toggle_y"] = "1021",
            ["hidden"] = "true",
        };

        var s = OverlaySettings.FromValues(values);

        Assert.AreEqual(OverlayActivation.Dwell, s.Activation);
        Assert.AreEqual(OverlaySettings.DefaultDwellMs, s.DwellMs, "키가 없으면 기본 800ms");
        Assert.IsTrue(s.Hidden);
        Assert.IsTrue(s.ToggleVisible);
        Assert.IsFalse(s.Locked);
        Assert.AreEqual(new ScreenPoint(254, 1021), s.TogglePosition);
        Assert.AreEqual(new ScreenPoint(469, 1010), s.Layout["dbc44eafbb44ea28"]);
    }

    [TestMethod]
    public void Bad_values_fall_back_like_pyqt5()
    {
        var s = OverlaySettings.FromValues(new Dictionary<string, string>
        {
            ["interaction_mode"] = "hover",
            ["dwell_ms"] = "fast",
            ["hidden"] = "yes",
            ["locked"] = "1",
            ["layout"] = """[{"profile_id": "a", "x": 1, "y": 2}, {"x": 5}, "junk", {"profile_id": "b", "x": "no", "y": 3}]""",
        });

        Assert.AreEqual(OverlayActivation.Click, s.Activation);
        Assert.AreEqual(800, s.DwellMs);
        Assert.IsFalse(s.Hidden, "true/True/1 만 참이다");
        Assert.IsTrue(s.Locked);
        CollectionAssert.AreEqual(new[] { "a" }, s.Layout.Keys.ToArray(), "깨진 항목만 버린다");

        Assert.IsEmpty(OverlaySettings.FromValues(new Dictionary<string, string> { ["layout"] = "{not json" }).Layout);
    }

    [TestMethod]
    public void Dwell_is_clamped_to_the_range_the_input_allowed()
    {
        Assert.AreEqual(200, OverlaySettings.FromValues(new Dictionary<string, string> { ["dwell_ms"] = "50" }).DwellMs);
        Assert.AreEqual(5000, new OverlaySettings { DwellMs = 99999 }.DwellMs);
    }

    [TestMethod]
    public void Values_round_trip_and_positions_can_be_left_out()
    {
        var original = new OverlaySettings
        {
            Activation = OverlayActivation.Dwell, DwellMs = 1200, Hidden = true, ToggleVisible = true, Locked = true,
            TogglePosition = new ScreenPoint(-300, 40),
        };
        original.Layout["p1"] = new ScreenPoint(10, -20);

        var copy = OverlaySettings.FromValues(original.ToValues());
        Assert.AreEqual((OverlayActivation.Dwell, 1200, true, true, true),
            (copy.Activation, copy.DwellMs, copy.Hidden, copy.ToggleVisible, copy.Locked));
        Assert.AreEqual(new ScreenPoint(-300, 40), copy.TogglePosition);
        Assert.AreEqual(new ScreenPoint(10, -20), copy.Layout["p1"]);

        var flagsOnly = OverlaySettings.FromValues(original.ToValues(), includePositions: false);
        Assert.IsNull(flagsOnly.TogglePosition);
        Assert.IsEmpty(flagsOnly.Layout);
        Assert.AreEqual(1200, flagsOnly.DwellMs);
    }

    [TestMethod]
    public void Shell_windows_and_hidden_windows_are_never_the_overlay_target()
    {
        Assert.IsFalse(ForegroundRules.IsTrackable("Shell_TrayWnd", true));
        Assert.IsFalse(ForegroundRules.IsTrackable("Progman", true));
        Assert.IsFalse(ForegroundRules.IsTrackable("Notepad", false));
        Assert.IsTrue(ForegroundRules.IsTrackable("Notepad", true));
    }
}
