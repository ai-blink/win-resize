using System.Windows.Input;

namespace WindowResizer.App.Tests;

/// <summary>
/// 감지 규칙(<see cref="HotkeyCapture"/>)과 선택 줄(<see cref="HotkeyPicker"/>). 실제 키보드 이벤트 대신 키와 수정키를 직접 준다
/// (WPF 컨트롤은 STA 스레드에서 만든다).
/// </summary>
[TestClass]
public sealed class HotkeyCaptureTests
{
    [TestMethod]
    public void Pressing_modifiers_and_a_key_gives_the_stored_combination_string()
    {
        Assert.AreEqual(CaptureOutcome.Set, HotkeyCapture.Interpret(Key.E, ModifierKeys.Control | ModifierKeys.Alt, out var text));
        Assert.AreEqual("Ctrl+Alt+E", text);

        HotkeyCapture.Interpret(Key.F5, ModifierKeys.Shift, out text);
        Assert.AreEqual("Shift+F5", text);

        HotkeyCapture.Interpret(Key.D7, ModifierKeys.Control, out text);
        Assert.AreEqual("Ctrl+7", text);

        HotkeyCapture.Interpret(Key.PageUp, ModifierKeys.Control | ModifierKeys.Windows, out text);
        Assert.AreEqual("Ctrl+Win+Page Up", text);

        // 다섯 개: 수정키 넷 + 주 키 하나(Windows 전역 단축키의 최대).
        HotkeyCapture.Interpret(Key.F23, ModifierKeys.Control | ModifierKeys.Alt | ModifierKeys.Shift | ModifierKeys.Windows, out text);
        Assert.AreEqual("Ctrl+Alt+Shift+Win+F23", text);
    }

    [TestMethod]
    public void A_modifier_alone_waits_and_an_unnameable_key_is_ignored()
    {
        Assert.AreEqual(CaptureOutcome.Waiting, HotkeyCapture.Interpret(Key.LeftCtrl, ModifierKeys.Control, out var text));
        Assert.IsNull(text);
        Assert.AreEqual(CaptureOutcome.Waiting, HotkeyCapture.Interpret(Key.RWin, ModifierKeys.Windows, out _));

        Assert.AreEqual(CaptureOutcome.Ignored, HotkeyCapture.Interpret(Key.OemComma, ModifierKeys.Control, out text));
        Assert.IsNull(text);
    }

    [TestMethod]
    public void Delete_or_backspace_alone_clears_but_with_a_modifier_it_is_a_key()
    {
        Assert.AreEqual(CaptureOutcome.Cleared, HotkeyCapture.Interpret(Key.Delete, ModifierKeys.None, out var text));
        Assert.AreEqual("", text);
        Assert.AreEqual(CaptureOutcome.Cleared, HotkeyCapture.Interpret(Key.Back, ModifierKeys.None, out _));

        Assert.AreEqual(CaptureOutcome.Set, HotkeyCapture.Interpret(Key.Delete, ModifierKeys.Control | ModifierKeys.Alt, out text));
        Assert.AreEqual("Ctrl+Alt+Delete", text);
    }

    [TestMethod]
    public void Tab_and_alt_f4_pass_through_so_the_keyboard_can_leave_and_close_the_window()
    {
        Assert.AreEqual(CaptureOutcome.PassThrough, HotkeyCapture.Interpret(Key.Tab, ModifierKeys.None, out _));
        Assert.AreEqual(CaptureOutcome.PassThrough, HotkeyCapture.Interpret(Key.Tab, ModifierKeys.Shift, out _));
        Assert.AreEqual(CaptureOutcome.PassThrough, HotkeyCapture.Interpret(Key.F4, ModifierKeys.Alt, out _));

        Assert.AreEqual(CaptureOutcome.Set, HotkeyCapture.Interpret(Key.Tab, ModifierKeys.Control, out var text), "Ctrl+Tab 은 단축키로 쓸 수 있다");
        Assert.AreEqual("Ctrl+Tab", text);
    }

    [STATestMethod]
    public void The_picker_shows_the_text_as_chips_and_a_key_and_builds_the_text_back_from_them()
    {
        var picker = new HotkeyPicker { Text = "Ctrl+Alt+E" };
        var chips = Chips(picker);

        Assert.AreEqual((true, true, false, false), (chips.ctrl.IsChecked == true, chips.alt.IsChecked == true, chips.shift.IsChecked == true, chips.win.IsChecked == true));
        Assert.AreEqual("E", chips.key.SelectedItem);

        // 손으로 고른다: Shift 를 켜고 키를 F5 로 바꾼다.
        chips.shift.IsChecked = true;
        Assert.AreEqual("Ctrl+Alt+Shift+E", picker.Text);
        chips.key.SelectedItem = "F5";
        Assert.AreEqual("Ctrl+Alt+Shift+F5", picker.Text);

        // 덜 고른 상태도 그대로 보인다(검사는 쓰는 쪽이 한다).
        picker.Text = "Ctrl+Alt";
        Assert.IsNull(chips.key.SelectedItem);
        Assert.IsTrue(chips.alt.IsChecked);

        picker.Text = "";
        Assert.AreEqual((false, false, false, false), (chips.ctrl.IsChecked == true, chips.alt.IsChecked == true, chips.shift.IsChecked == true, chips.win.IsChecked == true));
    }

    [STATestMethod]
    public void Detection_reports_start_and_stop_and_the_picker_turns_the_input_method_off()
    {
        var picker = new HotkeyPicker();
        var events = new List<bool>();
        picker.DetectingChanged += (_, on) => events.Add(on);
        var detect = (System.Windows.Controls.Button)picker.FindName("DetectButton")!;

        detect.RaiseEvent(new System.Windows.RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent));
        Assert.IsTrue(picker.IsDetecting);
        detect.RaiseEvent(new System.Windows.RoutedEventArgs(System.Windows.Controls.Primitives.ButtonBase.ClickEvent));
        Assert.IsFalse(picker.IsDetecting, "다시 누르면 취소한다");
        CollectionAssert.AreEqual(new[] { true, false }, events);

        Assert.IsFalse(InputMethod.GetIsInputMethodEnabled(picker), "한글 입력기가 글자 키를 먹으면 키가 오지 않는다");
    }

    private static (System.Windows.Controls.Primitives.ToggleButton ctrl, System.Windows.Controls.Primitives.ToggleButton alt,
        System.Windows.Controls.Primitives.ToggleButton shift, System.Windows.Controls.Primitives.ToggleButton win,
        System.Windows.Controls.ComboBox key) Chips(HotkeyPicker picker) => (
            (System.Windows.Controls.Primitives.ToggleButton)picker.FindName("CtrlChip")!,
            (System.Windows.Controls.Primitives.ToggleButton)picker.FindName("AltChip")!,
            (System.Windows.Controls.Primitives.ToggleButton)picker.FindName("ShiftChip")!,
            (System.Windows.Controls.Primitives.ToggleButton)picker.FindName("WinChip")!,
            (System.Windows.Controls.ComboBox)picker.FindName("KeyBox")!);
}
