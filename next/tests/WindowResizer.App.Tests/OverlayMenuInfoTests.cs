using WindowResizer.App.Overlay;
using WindowResizer.Core.Overlay;

namespace WindowResizer.App.Tests;

/// <summary>오버레이 버튼 우클릭 메뉴의 위치 줄(화면 요소 없이 문자열만).</summary>
[TestClass]
public sealed class OverlayMenuInfoTests
{
    private static string T(string key) => key switch
    {
        "Overlay.Menu.Position" => "P {0},{1} {2}x{3}",
        "Status.MaximizedMark" => "[max]",
        _ => key,
    };

    [TestMethod]
    public void The_position_line_shows_the_saved_place_and_size()
    {
        var button = new OverlayButton { X = 0, Y = 10, Width = 960, Height = 1040 };
        Assert.AreEqual("P 0,10 960x1040", OverlayMenuInfo.Position(button, T));
    }

    [TestMethod]
    public void A_button_without_a_place_says_so_and_a_maximized_one_carries_the_mark()
    {
        Assert.AreEqual("Overlay.Menu.NoPosition", OverlayMenuInfo.Position(new OverlayButton(), T));
        Assert.EndsWith("[max]", OverlayMenuInfo.Position(new OverlayButton { Width = 1, Height = 2, IsMaximized = true }, T));
    }
}
