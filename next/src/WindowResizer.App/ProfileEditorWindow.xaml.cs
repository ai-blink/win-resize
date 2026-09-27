using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using WindowResizer.App.ViewModels;

namespace WindowResizer.App;

/// <summary>프로필 편집 창. 검사와 되쓰기는 <see cref="ProfileEditorViewModel"/> 이 하고, 여기서는 창을 닫기만 한다.</summary>
public partial class ProfileEditorWindow : Window
{
    public ProfileEditorWindow()
    {
        InitializeComponent();
    }

    private void OnSave(object sender, RoutedEventArgs e)
    {
        // Enter(IsDefault)로 저장하면 초점이 있던 텍스트 상자의 값이 아직 원본에 안 갔을 수 있다.
        if (Keyboard.FocusedElement is TextBox box)
            box.GetBindingExpression(TextBox.TextProperty)?.UpdateSource();

        if (((ProfileEditorViewModel)DataContext).TrySave()) DialogResult = true;
    }
}
