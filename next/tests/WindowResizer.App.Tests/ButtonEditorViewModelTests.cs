using WindowResizer.App.ViewModels;
using WindowResizer.Core.Overlay;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.Tests;

[TestClass]
public sealed class ButtonEditorViewModelTests
{
    private static ButtonEditorViewModel Make(OverlayButton? button = null, WindowConfiguration? capture = null) =>
        new(button ?? new OverlayButton { Id = "a", Name = "Blender", X = 1, Y = 2, Width = 300, Height = 200 },
            () => capture, k => k);

    [TestMethod]
    public void Saving_writes_every_field_back_to_the_copy_and_normalizes_the_style()
    {
        var vm = Make();
        vm.Name = "  Chrome  ";
        (vm.X, vm.Y, vm.Width, vm.Height, vm.IsMaximized) = (-5, 6, 700, 500, true);
        vm.Shape = "circle";
        vm.Activation = "dwell";
        vm.DwellSeconds = 1.5;
        (vm.ButtonWidth, vm.ButtonHeight) = (200, 60);
        vm.BackgroundColor = "#ABCDEF";

        Assert.IsTrue(vm.TrySave());

        var b = vm.Button;
        Assert.AreEqual(("Chrome", -5, 6, 700, 500, true), (b.Name, b.X, b.Y, b.Width, b.Height, b.IsMaximized));
        Assert.AreEqual(("circle", "dwell", 1500, 200, 60), (b.Style.Shape, b.Style.Activation, b.Style.DwellMs, b.Style.Width, b.Style.Height));
        Assert.AreEqual("#abcdef", b.Style.BackgroundColor, "색은 소문자 한 가지로 맞춘다");
    }

    [TestMethod]
    public void Bad_values_are_refused_with_a_reason_and_leave_the_copy_alone()
    {
        var vm = Make();

        vm.Name = " ";
        Assert.IsFalse(vm.TrySave());
        Assert.AreEqual("Editor.Error.NameEmpty", vm.Error);
        vm.Name = "ok";

        vm.Width = 0;
        Assert.IsFalse(vm.TrySave());
        Assert.AreEqual("Editor.Error.SizeInvalid", vm.Error);
        vm.Width = 300;

        vm.DwellSeconds = 9;
        Assert.IsFalse(vm.TrySave());
        Assert.AreEqual("ButtonEditor.Error.Dwell", vm.Error);
        vm.DwellSeconds = 0;

        vm.ButtonWidth = 10;
        Assert.IsFalse(vm.TrySave());
        Assert.AreEqual("ButtonEditor.Error.ButtonSize", vm.Error);
        vm.ButtonWidth = 150;

        vm.TextColor = "red";
        Assert.IsFalse(vm.TrySave());
        Assert.AreEqual("ButtonEditor.Error.Color", vm.Error);
        vm.TextColor = "#fff";

        Assert.AreEqual("Blender", vm.Button.Name, "실패한 동안 복사본은 그대로다");
        Assert.IsTrue(vm.TrySave());
        Assert.AreEqual("", vm.Error);
    }

    [TestMethod]
    public void Take_from_the_last_window_fills_the_place_or_says_nothing_was_found()
    {
        var vm = Make(capture: new WindowConfiguration { X = 10, Y = 20, Width = 800, Height = 600, IsMaximized = true });
        vm.CaptureFromWindowCommand.Execute(null);
        Assert.AreEqual((10, 20, 800, 600, true), (vm.X, vm.Y, vm.Width, vm.Height, vm.IsMaximized));
        Assert.AreEqual("ButtonEditor.Captured", vm.Message);

        var none = Make(capture: null);
        none.CaptureFromWindowCommand.Execute(null);
        Assert.AreEqual((1, 2, 300, 200), (none.X, none.Y, none.Width, none.Height));
        Assert.AreEqual("ButtonEditor.CaptureFailed", none.Message);
    }

    [TestMethod]
    public void Visible_fields_raise_a_preview_of_the_current_input_and_other_fields_do_not()
    {
        var vm = Make();
        var previews = new List<OverlayButton>();
        vm.Previewed += previews.Add;

        vm.Shape = "circle";
        vm.ButtonWidth = 999;             // 범위 밖: 저장은 거절되지만 미리보기는 저장 때와 같이 보정해 그린다
        vm.BackgroundColor = "not-a-colour";
        vm.Name = " ";                    // 비면 원래 이름으로 그린다
        vm.X = 5;                         // 위치는 그림이 아니다
        vm.DwellSeconds = 2;

        Assert.HasCount(4, previews);
        var last = previews[^1];
        Assert.AreEqual(("Blender", "circle", 600, "not-a-colour"), (last.Name, last.Style.Shape, last.Style.Width, last.Style.BackgroundColor));
        Assert.AreEqual(150, vm.Button.Style.Width, "미리보기는 편집 중인 복사본을 바꾸지 않는다");
        Assert.AreEqual("Blender", vm.Button.Name);
    }
}
