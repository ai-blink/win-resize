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

    public void Warn(string title, string message)
    {
        var owner = Owner();
        if (owner is null) MessageBox.Show(message, title, MessageBoxButton.OK, MessageBoxImage.Warning);
        else MessageBox.Show(owner, message, title, MessageBoxButton.OK, MessageBoxImage.Warning);
    }

    public bool ShowEditor(ProfileEditorViewModel editor) =>
        new ProfileEditorWindow { DataContext = editor, Owner = Owner() }.ShowDialog() == true;

    public WindowRow? ChooseWindow(IReadOnlyList<WindowRow> candidates)
    {
        var picker = new WindowPickerWindow(candidates) { Owner = Owner() };
        return picker.ShowDialog() == true ? picker.Selected : null;
    }

    public bool CopyToClipboard(string text)
    {
        try
        {
            // 다른 프로그램이 클립보드를 쥐고 있으면 COMException 이 난다. 두 번째 인자 true 는 짧게 다시 시도한다.
            Clipboard.SetDataObject(text, copy: true);
            return true;
        }
        catch (System.Runtime.InteropServices.COMException)
        {
            return false;
        }
    }

    public string? ChooseSaveFile(string title, string suggestedFileName, string filter)
    {
        var dialog = new Microsoft.Win32.SaveFileDialog { Title = title, FileName = suggestedFileName, Filter = filter, AddExtension = true };
        var owner = Owner();
        var ok = owner is null ? dialog.ShowDialog() : dialog.ShowDialog(owner);
        return ok == true ? dialog.FileName : null;
    }

    public string? OpenFolder(string path)
    {
        try
        {
            if (!System.IO.Directory.Exists(path)) return string.Format(text("Status.FolderMissing"), path);
            // UseShellExecute 로 탐색기가 열린다. 경로에 공백이 있어도 한 인자로 간다.
            System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo(path) { UseShellExecute = true });
            return null;
        }
        catch (Exception ex) when (ex is System.ComponentModel.Win32Exception or InvalidOperationException)
        {
            return ex.Message;
        }
    }

    private static Window? Owner() =>
        Application.Current.Windows.OfType<Window>().FirstOrDefault(w => w.IsActive) ?? Application.Current.MainWindow;
}
