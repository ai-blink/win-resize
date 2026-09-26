using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Profiles;
using WindowResizer.Core.Windowing;

namespace WindowResizer.Core.Tests;

[TestClass]
public sealed class HotkeyCombinationTests
{
    // tests/test_profile_hotkeys.py test_hotkey_parser_accepts_editor_combination
    [TestMethod]
    public void Parser_accepts_the_editor_combination()
    {
        var combination = HotkeyCombination.Parse("Ctrl + Alt + E");

        Assert.AreEqual(HotkeyModifiers.Control | HotkeyModifiers.Alt, combination.Modifiers);
        Assert.AreEqual('E', combination.VirtualKey);
    }

    [TestMethod]
    public void Function_digit_and_named_keys_map_to_virtual_keys()
    {
        Assert.AreEqual(0x70, HotkeyCombination.Parse("F1").VirtualKey);
        Assert.AreEqual(0x87, HotkeyCombination.Parse("ctrl+f24").VirtualKey);
        Assert.AreEqual('7', HotkeyCombination.Parse("Shift+7").VirtualKey);
        Assert.AreEqual('A', HotkeyCombination.Parse("win+a").VirtualKey);
        Assert.AreEqual(0x21, HotkeyCombination.Parse("Ctrl+Page Up").VirtualKey);
        Assert.AreEqual(0x1B, HotkeyCombination.Parse("Alt+Esc").VirtualKey);
        Assert.AreEqual(HotkeyModifiers.None, HotkeyCombination.Parse("F5").Modifiers);
    }

    [TestMethod]
    public void Invalid_combinations_are_rejected_with_a_reason()
    {
        foreach (var bad in new[] { "", "   ", "Ctrl+Alt", "Ctrl+Ctrl+E", "Ctrl+E+F", "F25", "F0", "Ctrl+ㄱ", "Ctrl+Nope" })
        {
            Assert.IsFalse(HotkeyCombination.TryParse(bad, out _), "거절돼야 한다: '" + bad + "'");
        }
    }
}

[TestClass]
public sealed class WindowListFilterTests
{
    private static readonly PixelRect Sized = new(0, 0, 800, 600);

    [TestMethod]
    public void Ordinary_titled_window_is_listed()
    {
        Assert.IsTrue(WindowListFilter.IsUserWindow(new WindowInfo(Title: "Untitled - Notepad", ClassName: "Notepad"), Sized));
    }

    [TestMethod]
    public void System_classes_titles_blank_titles_and_zero_size_are_hidden()
    {
        Assert.IsFalse(WindowListFilter.IsUserWindow(new WindowInfo(Title: "x", ClassName: "Shell_TrayWnd"), Sized));
        Assert.IsFalse(WindowListFilter.IsUserWindow(new WindowInfo(Title: "Program Manager", ClassName: "Progman"), Sized));
        Assert.IsFalse(WindowListFilter.IsUserWindow(new WindowInfo(Title: "Desktop", ClassName: "Other"), Sized));
        Assert.IsFalse(WindowListFilter.IsUserWindow(new WindowInfo(Title: "   ", ClassName: "Other"), Sized));
        Assert.IsFalse(WindowListFilter.IsUserWindow(new WindowInfo(Title: "x", ClassName: "Other"), new PixelRect(0, 0, 0, 600)));
    }

    [TestMethod]
    public void Class_match_is_exact_not_substring_like_python()
    {
        // PyQt5 _is_system_window 은 `class_name.lower() in system_classes` - 부분 일치가 아니다.
        Assert.IsTrue(WindowListFilter.IsUserWindow(new WindowInfo(Title: "x", ClassName: "MyButtonHost"), Sized));
    }
}
