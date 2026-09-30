using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using WindowResizer.App.ViewModels;

namespace WindowResizer.App;

/// <summary>오버레이 버튼 속성 창. 검사와 되쓰기는 <see cref="ButtonEditorViewModel"/> 이 하고, 여기서는 창을 닫기만 한다.</summary>
public partial class ButtonEditorWindow : Window
{
    public ButtonEditorWindow()
    {
        InitializeComponent();
        Theming.UiScale.Attach(this);
        DataContextChanged += (_, _) => Hook();
    }

    /// <summary>미리보기 그림(렌더 스모크 테스트가 크기를 잰다).</summary>
    public FrameworkElement PreviewElement => PreviewFace;

    private ButtonEditorViewModel? _hooked;

    /// <summary>
    /// 미리보기를 편집 값에 잇는다. 창 전체에 앱 배율이 걸려 있어서(<see cref="Theming.UiScale"/>) 그대로 두면 미리보기가
    /// 배율만큼 커지거나 작아진다. 미리보기 칸에만 역배율을 걸어 화면에 뜨는 버튼과 같은 크기로 보인다.
    /// </summary>
    private void Hook()
    {
        if (_hooked is not null) _hooked.Previewed -= Draw;
        _hooked = DataContext as ButtonEditorViewModel;
        if (_hooked is null) return;

        var inverse = 1.0 / Math.Max(0.01, Theming.UiScale.Factor);
        PreviewHost.LayoutTransform = new System.Windows.Media.ScaleTransform(inverse, inverse);
        _hooked.Previewed += Draw;
        Draw(_hooked.BuildPreview());
    }

    private void Draw(WindowResizer.Core.Overlay.OverlayButton preview) =>
        PreviewFace.Draw(preview.Style, preview.Name, hovered: false, progress: 0, feedback: null);

    private void OnSave(object sender, RoutedEventArgs e)
    {
        // Enter(IsDefault)로 저장하면 초점이 있던 텍스트 상자의 값이 아직 원본에 안 갔을 수 있다.
        if (Keyboard.FocusedElement is TextBox box)
            box.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();

        if (((ButtonEditorViewModel)DataContext).TrySave()) DialogResult = true;
    }
}
