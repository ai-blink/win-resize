using WindowResizer.App.Overlay;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.Tests;

/// <summary>오버레이 버튼 우클릭 메뉴의 연결 대상 줄(화면 요소 없이 문자열만).</summary>
[TestClass]
public sealed class OverlayMenuInfoTests
{
    private static string T(string key) => key switch
    {
        "Overlay.Menu.Position" => "P {0},{1} {2}x{3}",
        "Overlay.Menu.Title" => "title:{0}",
        "Overlay.Menu.Process" => "proc:{0}",
        "Status.MaximizedMark" => "[max]",
        _ => key,
    };

    private static Profile Make(MatchingCriteria? criteria, WindowConfiguration? config = null) =>
        new() { Name = "n", MatchingCriteria = criteria, WindowConfig = config };

    [TestMethod]
    public void Executable_path_shows_file_name_with_strategy_then_the_full_path_and_the_saved_position()
    {
        var info = OverlayMenuInfo.Describe(
            Make(new MatchingCriteria { Strategy = MatchingStrategy.ExecutablePath, ExecutablePathPattern = @"C:\Program Files\Google\Chrome\chrome.exe" },
                new WindowConfiguration { X = 0, Y = 10, Width = 960, Height = 1040 }), T);

        CollectionAssert.AreEqual(new[] { "chrome.exe (Strategy.ExecutablePath)", @"C:\Program Files\Google\Chrome\chrome.exe" }, info.Target.ToArray());
        Assert.AreEqual("P 0,10 960x1040", info.Position);
    }

    [TestMethod]
    public void Title_and_process_strategies_show_their_pattern()
    {
        var title = OverlayMenuInfo.Describe(Make(new MatchingCriteria { Strategy = MatchingStrategy.TitleContains, WindowTitlePattern = "Memo" }), T);
        CollectionAssert.AreEqual(new[] { "Strategy.TitleContains", "Memo" }, title.Target.ToArray());

        var process = OverlayMenuInfo.Describe(Make(new MatchingCriteria { Strategy = MatchingStrategy.ProcessName, ProcessNamePattern = "blender" }), T);
        CollectionAssert.AreEqual(new[] { "Strategy.ProcessName", "blender" }, process.Target.ToArray());
    }

    [TestMethod]
    public void Combined_lists_only_the_filled_conditions()
    {
        var info = OverlayMenuInfo.Describe(
            Make(new MatchingCriteria { Strategy = MatchingStrategy.Combined, WindowTitlePattern = "A", ProcessNamePattern = "b" }), T);
        CollectionAssert.AreEqual(new[] { "Strategy.Combined", "title:A", "proc:b" }, info.Target.ToArray());
    }

    [TestMethod]
    public void Missing_pieces_never_throw_and_are_marked()
    {
        var info = OverlayMenuInfo.Describe(Make(null), T);
        CollectionAssert.AreEqual(new[] { "Overlay.Menu.Empty" }, info.Target.ToArray());
        Assert.AreEqual("Overlay.Menu.NoPosition", info.Position);

        var empty = OverlayMenuInfo.Describe(Make(new MatchingCriteria { Strategy = MatchingStrategy.ExecutablePath }), T);
        CollectionAssert.AreEqual(new[] { "Strategy.ExecutablePath", "Overlay.Menu.Empty" }, empty.Target.ToArray());

        var smart = OverlayMenuInfo.Describe(Make(new MatchingCriteria { Strategy = MatchingStrategy.Smart }), T);
        CollectionAssert.AreEqual(new[] { "Smart" }, smart.Target.ToArray());
    }

    [TestMethod]
    public void Maximized_windows_carry_the_mark()
    {
        var info = OverlayMenuInfo.Describe(Make(null, new WindowConfiguration { Width = 1, Height = 2, IsMaximized = true }), T);
        Assert.EndsWith("[max]", info.Position);
    }
}
