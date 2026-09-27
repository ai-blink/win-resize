using System.Windows;
using WindowResizer.App.ViewModels;

namespace WindowResizer.App;

/// <summary>
/// <see cref="IDialogService"/> 의 WPF 구현. 소유 창은 지금 활성 창이다 - 편집 창 안에서 창 고르기를 열면
/// 편집 창이 주인이 된다.
/// </summary>
public sealed class DialogService(Func<string, string> text) : IDialogService
{
    public bool ConfirmDelete(string profileName)
    {
        var message = string.Format(text("Confirm.Delete"), profileName);
        var title = text("Confirm.Delete.Title");
        var owner = Owner();
        var answer = owner is null
            ? MessageBox.Show(message, title, MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No)
            : MessageBox.Show(owner, message, title, MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No);
        return answer == MessageBoxResult.Yes;
    }

    public bool ShowEditor(ProfileEditorViewModel editor) =>
        new ProfileEditorWindow { DataContext = editor, Owner = Owner() }.ShowDialog() == true;

    public WindowRow? ChooseWindow(IReadOnlyList<WindowRow> candidates)
    {
        var picker = new WindowPickerWindow(candidates) { Owner = Owner() };
        return picker.ShowDialog() == true ? picker.Selected : null;
    }

    private static Window? Owner() =>
        Application.Current.Windows.OfType<Window>().FirstOrDefault(w => w.IsActive) ?? Application.Current.MainWindow;
}
