using WindowResizer.Core.Overlay;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Tests;

[TestClass]
public sealed class OverlayButtonTests
{
    [TestMethod]
    public void Buttons_round_trip_through_the_saved_values_with_their_own_place_and_style()
    {
        var settings = new OverlaySettings { ButtonsMigrated = true };
        settings.Buttons.Add(new OverlayButton
        {
            Id = "a", Name = "Blender", X = 225, Y = 434, Width = 2457, Height = 1515, IsMaximized = true,
            Style = new OverlayStyle { Enabled = true, Shape = "circle", Label = "B", DwellMs = 1500 },
        });

        var read = OverlaySettings.FromValues(settings.ToValues());

        Assert.IsTrue(read.ButtonsMigrated);
        var button = read.Buttons.Single();
        Assert.AreEqual(("a", "Blender", 225, 434, 2457, 1515, true), (button.Id, button.Name, button.X, button.Y, button.Width, button.Height, button.IsMaximized));
        Assert.AreEqual(("circle", "B", 1500), (button.Style.Shape, button.Style.Label, button.Style.DwellMs));
        Assert.IsTrue(button.HasPlace);
    }

    [TestMethod]
    public void Broken_lists_and_entries_are_dropped_and_duplicates_keep_the_first()
    {
        var values = new Dictionary<string, string> { ["buttons"] = "not json" };
        Assert.IsEmpty(OverlaySettings.FromValues(values).Buttons);

        values["buttons"] = """
            [ {"id":"a","name":"one","x":1,"y":2,"width":3,"height":4},
              {"id":"","name":"no id"},
              {"id":"a","name":"dup"},
              {"id":"c","name":"bad","x":"text"},
              5,
              {"id":"d","name":"two","width":9,"height":9,"style":{"shape":"weird","width":5000}} ]
            """;
        var buttons = OverlaySettings.FromValues(values).Buttons;

        CollectionAssert.AreEqual(new[] { "a", "d" }, buttons.Select(b => b.Id).ToArray());
        Assert.AreEqual("one", buttons[0].Name);
        Assert.AreEqual(("pill", 600), (buttons[1].Style.Shape, buttons[1].Style.Width), "생김새는 읽을 때 보정된다");
    }

    [TestMethod]
    public void A_profile_copies_into_a_button_that_keeps_its_id_so_the_old_layout_still_applies()
    {
        var profile = new Profile
        {
            Name = "Chrome",
            WindowConfig = new WindowConfiguration { X = 5, Y = 6, Width = 700, Height = 500, IsMaximized = true, Opacity = 0.5, AlwaysOnTop = true },
            OverlayStyle = new OverlayStyle { Enabled = true, Shape = "rounded", BackgroundColor = "#123456" },
        };

        var button = OverlayButton.FromProfile("p1", profile)!;

        Assert.AreEqual(("p1", "Chrome", 5, 6, 700, 500, true), (button.Id, button.Name, button.X, button.Y, button.Width, button.Height, button.IsMaximized));
        Assert.AreEqual(("rounded", "#123456"), (button.Style.Shape, button.Style.BackgroundColor));
        var config = button.ToWindowConfiguration();
        Assert.AreEqual((0.0, false), (config.Opacity, config.AlwaysOnTop), "버튼은 투명도와 항상 위를 건드리지 않는다");
        Assert.AreNotSame(profile.OverlayStyle, button.Style, "프로필의 스타일 객체를 공유하지 않는다");
    }

    [TestMethod]
    public void A_profile_without_a_usable_place_gives_no_button()
    {
        Assert.IsNull(OverlayButton.FromProfile("p", new Profile { Name = "x" }));
        Assert.IsNull(OverlayButton.FromProfile("p", new Profile { Name = "x", WindowConfig = new WindowConfiguration { Width = 0, Height = 10 } }));
    }

    [TestMethod]
    public void A_clone_does_not_share_its_style()
    {
        var original = new OverlayButton { Id = "a", Style = new OverlayStyle { Enabled = true, Label = "x" } };
        var copy = original.Clone();
        copy.Style.Label = "y";
        copy.Name = "other";

        Assert.AreEqual("x", original.Style.Label);
        Assert.AreEqual("", original.Name);
    }
}
