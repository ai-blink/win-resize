using System.Text.RegularExpressions;
using System.Windows.Input;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Overlay;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.ViewModels;

/// <summary>버튼 속성 창 사이드바 항목(new-alt 속성창의 순서: 일반, 크기 및 위치, 동작, 외형).</summary>
public enum ButtonPage
{
    General,
    Position,
    Behavior,
    Look,
}

/// <summary>
/// 오버레이 버튼 속성 창(D-032). 프로필 편집 창과 같은 규율: <b>복사본</b>을 받아 필드로 풀어 두고,
/// <see cref="TrySave"/> 가 검사를 통과했을 때만 복사본에 되쓴다. 문서(설정)에 넣는 것은 <see cref="MainViewModel"/> 의 일이다.
/// </summary>
public sealed class ButtonEditorViewModel : ObservableObject
{
    public static readonly string[] Shapes = OverlayStyle.Shapes;
    public static readonly string[] Activations = OverlayStyle.Activations;

    private static readonly Regex HexColor = new("^#([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$", RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private readonly Func<WindowConfiguration?> _captureTarget;
    private readonly Func<string, string> _text;
    private readonly Func<(WindowConfiguration Configuration, string Title)?>? _pickOnScreen;

    private ButtonPage _page;
    private string _name, _label, _activation, _shape, _background, _foreground, _border;
    private int _x, _y, _width, _height, _buttonWidth, _buttonHeight;
    private bool _isMaximized;
    private double _dwellSeconds;
    private string _error = "", _message = "";

    /// <param name="captureTarget">직전에 쓰던 창의 지금 자리. 잡지 못하면 null(이유는 호출한 쪽이 상태 줄로 알렸다).</param>
    /// <param name="pickOnScreen">화면에서 창을 골라 그 자리와 제목을 돌려준다. 취소하거나 잡지 못하면 null(이유는 호출한 쪽이 알렸다).</param>
    public ButtonEditorViewModel(OverlayButton working, Func<WindowConfiguration?> captureTarget, Func<string, string> text,
        Func<(WindowConfiguration Configuration, string Title)?>? pickOnScreen = null)
    {
        _pickOnScreen = pickOnScreen;
        Button = working;
        _captureTarget = captureTarget;
        _text = text;

        _name = working.Name;
        (_x, _y, _width, _height, _isMaximized) = (working.X, working.Y, working.Width, working.Height, working.IsMaximized);
        var s = working.Style;
        _label = s.Label;
        _activation = s.Activation;
        _dwellSeconds = s.DwellMs / 1000.0;
        _shape = s.Shape;
        (_buttonWidth, _buttonHeight) = (s.Width, s.Height);
        (_background, _foreground, _border) = (s.BackgroundColor, s.TextColor, s.BorderColor);

        NavigateCommand = new ParameterCommand<ButtonPage>(page => Page = page);
        CaptureFromWindowCommand = new RelayCommand(CaptureFromWindow);
        PickWindowCommand = new RelayCommand(PickWindow, () => _pickOnScreen is not null);
        PropertyChanged += (_, e) =>
        {
            if (e.PropertyName is nameof(Name) or nameof(Label) or nameof(Shape) or nameof(ButtonWidth) or nameof(ButtonHeight)
                or nameof(BackgroundColor) or nameof(TextColor) or nameof(BorderColor))
                Previewed?.Invoke(BuildPreview());
        };
    }

    /// <summary>
    /// 보이는 값(이름, 글자, 모양, 크기, 색)이 바뀔 때마다 지금 입력을 그대로 담은 버튼을 알린다. 속성 창의 미리보기와
    /// 화면에 떠 있는 실제 버튼이 이것을 그린다. 검사는 하지 않는다 - 저장 전이므로 틀린 입력도 그려 보이고,
    /// 범위 밖 크기는 저장할 때와 같이 보정해 그린다.
    /// </summary>
    public event Action<OverlayButton>? Previewed;

    /// <summary>지금 입력으로 그릴 버튼(복사본). 이름이 비었으면 원래 이름으로 그린다.</summary>
    public OverlayButton BuildPreview()
    {
        var preview = Button.Clone();
        preview.Name = string.IsNullOrWhiteSpace(Name) ? Button.Name : Name.Trim();
        var s = preview.Style;
        s.Label = Label.Trim();
        s.Shape = Shape;
        (s.Width, s.Height) = (ButtonWidth, ButtonHeight);
        (s.BackgroundColor, s.TextColor, s.BorderColor) = (BackgroundColor, TextColor, BorderColor);
        s.Normalize();
        return preview;
    }

    /// <summary>편집 중인 복사본. <see cref="TrySave"/> 성공 뒤에 새 값이 들어 있다.</summary>
    public OverlayButton Button { get; }

    public ICommand NavigateCommand { get; }
    public ICommand CaptureFromWindowCommand { get; }
    public ICommand PickWindowCommand { get; }

    public ButtonPage Page { get => _page; set => Set(ref _page, value); }
    public string Name { get => _name; set => Set(ref _name, value); }
    public string Label { get => _label; set => Set(ref _label, value); }
    public int X { get => _x; set => Set(ref _x, value); }
    public int Y { get => _y; set => Set(ref _y, value); }
    public int Width { get => _width; set => Set(ref _width, value); }
    public int Height { get => _height; set => Set(ref _height, value); }
    public bool IsMaximized { get => _isMaximized; set => Set(ref _isMaximized, value); }
    public string Activation { get => _activation; set => Set(ref _activation, value); }

    /// <summary>0 이면 전역 설정의 시간을 따른다.</summary>
    public double DwellSeconds { get => _dwellSeconds; set => Set(ref _dwellSeconds, value); }

    public string Shape { get => _shape; set => Set(ref _shape, value); }
    public int ButtonWidth { get => _buttonWidth; set => Set(ref _buttonWidth, value); }
    public int ButtonHeight { get => _buttonHeight; set => Set(ref _buttonHeight, value); }
    public string BackgroundColor { get => _background; set => Set(ref _background, value); }
    public string TextColor { get => _foreground; set => Set(ref _foreground, value); }
    public string BorderColor { get => _border; set => Set(ref _border, value); }

    public string Error { get => _error; private set => Set(ref _error, value); }
    public string Message { get => _message; private set => Set(ref _message, value); }

    private void CaptureFromWindow()
    {
        if (_captureTarget() is not { } c)
        {
            Message = _text("ButtonEditor.CaptureFailed");
            return;
        }
        (X, Y, Width, Height, IsMaximized) = (c.X, c.Y, c.Width, c.Height, c.IsMaximized);
        Message = _text("ButtonEditor.Captured");
    }

    private void PickWindow()
    {
        if (_pickOnScreen?.Invoke() is not { } picked) return;   // 취소는 조용히 - 아무것도 바꾸지 않는다
        var c = picked.Configuration;
        (X, Y, Width, Height, IsMaximized) = (c.X, c.Y, c.Width, c.Height, c.IsMaximized);
        Message = string.Format(_text("ButtonEditor.Picked"), picked.Title);
    }

    /// <summary>검사를 통과하면 복사본에 되쓰고 true. 아니면 <see cref="Error"/> 에 이유를 두고 false.</summary>
    public bool TrySave()
    {
        var error = Validate();
        Error = error ?? "";
        if (error is not null) return false;

        Button.Name = Name.Trim();
        (Button.X, Button.Y, Button.Width, Button.Height, Button.IsMaximized) = (X, Y, Width, Height, IsMaximized);
        var s = Button.Style;
        s.Label = Label.Trim();
        s.Activation = Activation;
        s.DwellMs = (int)Math.Round(DwellSeconds * 1000);
        s.Shape = Shape;
        (s.Width, s.Height) = (ButtonWidth, ButtonHeight);
        (s.BackgroundColor, s.TextColor, s.BorderColor) = (BackgroundColor, TextColor, BorderColor);
        s.Normalize();
        return true;
    }

    private string? Validate()
    {
        if (string.IsNullOrWhiteSpace(Name)) return _text("Editor.Error.NameEmpty");
        if (Width <= 0 || Height <= 0) return _text("Editor.Error.SizeInvalid");
        if (DwellSeconds != 0 && (DwellSeconds < 0.2 || DwellSeconds > 5.0)) return _text("ButtonEditor.Error.Dwell");
        if (ButtonWidth < 40 || ButtonWidth > 600 || ButtonHeight < 28 || ButtonHeight > 200) return _text("ButtonEditor.Error.ButtonSize");
        foreach (var color in new[] { BackgroundColor, TextColor, BorderColor })
            if (!HexColor.IsMatch((color ?? "").Trim())) return _text("ButtonEditor.Error.Color");
        return null;
    }
}
