using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using WindowResizer.Core.Hotkeys;

namespace WindowResizer.App;

/// <summary>
/// 단축키 하나를 고르는 한 줄: 수정키 칩 4개, 주 키 목록, 감지 버튼. 손으로 고르거나 감지로 채운다.
/// 값은 <see cref="Text"/> 하나(<c>Ctrl+Alt+E</c>)이고 저장 형식은 바뀌지 않는다.
///
/// 덜 고른 상태도 그대로 보인다(<c>Ctrl+Alt</c> - 주 키 없음): 검사는 쓰는 쪽이 하고, 여기서는 지금 상태를 지우지 않는다.
///
/// 감지: 버튼을 누르면 이 칸이 키를 기다린다(<see cref="IsDetecting"/>). 이미 등록된 조합을 누르면 등록이 먼저
/// 키를 잡아 가므로, 기다리는 동안 전역 등록을 풀어야 한다 - 그건 이 칸이 아니라 쓰는 쪽이
/// <see cref="DetectingChanged"/> 로 받아 처리한다(<c>HotkeysViewModel.SetCapturing</c>).
/// 다른 곳을 누르거나 초점이 나가면 감지를 멈춘다.
/// </summary>
public partial class HotkeyPicker : UserControl
{
    public static readonly DependencyProperty TextProperty = DependencyProperty.Register(
        nameof(Text), typeof(string), typeof(HotkeyPicker),
        new FrameworkPropertyMetadata("", FrameworkPropertyMetadataOptions.BindsTwoWayByDefault, (d, _) => ((HotkeyPicker)d).ShowText()));

    private bool _updating;
    private bool _detecting;

    public HotkeyPicker()
    {
        InitializeComponent();
        KeyBox.ItemsSource = HotkeyCombination.KeyNames;
        InputMethod.SetIsInputMethodEnabled(this, false);

        // Click 이 아니라 Checked/Unchecked 를 본다: 마우스, 키보드, 화면 읽기 도구(UI 자동화) 어느 쪽으로 켜도 같은 경로다.
        foreach (var chip in Chips)
        {
            chip.Checked += (_, _) => ComposeText();
            chip.Unchecked += (_, _) => ComposeText();
        }
        KeyBox.SelectionChanged += (_, _) => ComposeText();
        DetectButton.Click += (_, _) => SetDetecting(!_detecting);
        IsKeyboardFocusWithinChanged += (_, e) => { if (!(bool)e.NewValue) SetDetecting(false); };
        IsEnabledChanged += (_, _) => SetDetecting(false);
        Unloaded += (_, _) => SetDetecting(false);
        ShowDetectLabel();
    }

    public string Text
    {
        get => (string)GetValue(TextProperty);
        set => SetValue(TextProperty, value);
    }

    /// <summary>감지를 시작하거나 멈췄다. 인자 true 면 시작.</summary>
    public event EventHandler<bool>? DetectingChanged;

    public bool IsDetecting => _detecting;

    private IEnumerable<System.Windows.Controls.Primitives.ToggleButton> Chips => [CtrlChip, AltChip, ShiftChip, WinChip];

    /// <summary>칩과 주 키 목록을 지금 <see cref="Text"/> 에 맞춘다.</summary>
    private void ShowText()
    {
        if (_updating) return;
        _updating = true;
        try
        {
            var (modifiers, key) = HotkeyCombination.Split(Text);
            CtrlChip.IsChecked = (modifiers & HotkeyModifiers.Control) != 0;
            AltChip.IsChecked = (modifiers & HotkeyModifiers.Alt) != 0;
            ShiftChip.IsChecked = (modifiers & HotkeyModifiers.Shift) != 0;
            WinChip.IsChecked = (modifiers & HotkeyModifiers.Win) != 0;
            KeyBox.SelectedItem = key;
        }
        finally
        {
            _updating = false;
        }
    }

    /// <summary>칩과 목록에서 <see cref="Text"/> 를 만든다(사용자가 손으로 고쳤을 때).</summary>
    private void ComposeText()
    {
        if (_updating) return;
        var modifiers = HotkeyModifiers.None;
        if (CtrlChip.IsChecked == true) modifiers |= HotkeyModifiers.Control;
        if (AltChip.IsChecked == true) modifiers |= HotkeyModifiers.Alt;
        if (ShiftChip.IsChecked == true) modifiers |= HotkeyModifiers.Shift;
        if (WinChip.IsChecked == true) modifiers |= HotkeyModifiers.Win;

        _updating = true;
        try
        {
            Text = HotkeyCombination.Compose(modifiers, KeyBox.SelectedItem as string);
        }
        finally
        {
            _updating = false;
        }
    }

    private void SetDetecting(bool detecting)
    {
        if (_detecting == detecting) return;
        _detecting = detecting;
        ShowDetectLabel();
        if (detecting) DetectButton.Focus();
        DetectingChanged?.Invoke(this, detecting);
    }

    private void ShowDetectLabel() =>
        DetectButton.Content = TryFindResource(_detecting ? "Hotkeys.Detecting" : "Hotkeys.Detect") ?? (_detecting ? "..." : "Detect");

    protected override void OnPreviewKeyDown(KeyEventArgs e)
    {
        if (!_detecting)
        {
            base.OnPreviewKeyDown(e);
            return;
        }

        var key = e.Key switch
        {
            Key.System => e.SystemKey,
            Key.ImeProcessed => e.ImeProcessedKey,
            _ => e.Key,
        };
        switch (HotkeyCapture.Interpret(key, Keyboard.Modifiers, out var text))
        {
            case CaptureOutcome.PassThrough:
                return;
            case CaptureOutcome.Waiting or CaptureOutcome.Ignored:
                e.Handled = true;
                return;
            default:
                Text = text ?? "";
                e.Handled = true;
                SetDetecting(false);
                return;
        }
    }
}
