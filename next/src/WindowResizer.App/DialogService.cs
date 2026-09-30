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

    public bool ShowButtonEditor(ButtonEditorViewModel editor) =>
        new ButtonEditorWindow { DataContext = editor, Owner = Owner() }.ShowDialog() == true;

    /// <summary>
    /// 화면을 가리는 이 앱의 창(메인 창, 속성 창)은 고르는 동안 화면 밖으로 치우고 끝나면 제자리로 되돌린다. 버튼 창은
    /// 그대로 둔다 - 어차피 고를 수 없는 창이고, 치우면 깜박인다.
    /// <b>Visibility 로 숨기면 안 된다</b>: <c>ShowDialog</c> 로 뜬 속성 창을 숨기면 ShowDialog 가 결과 없이 돌아와, 다시
    /// 보여도 모달이 아닌 창이 되고 취소 버튼(<c>IsCancel</c>)이 예외로 죽는다(라이브로 확인). 위치만 옮긴다.
    /// </summary>
    public WindowRow? PickWindowOnScreen(IReadOnlyList<WindowRow> candidates)
    {
        var win32 = new Infrastructure.Windowing.Win32Windows();
        var moved = new List<(Window Window, nint Handle, Core.Windowing.PixelRect Rect)>();
        foreach (var w in Application.Current.Windows.OfType<Window>())
        {
            if (!w.IsVisible || w.WindowState == WindowState.Minimized ||
                w is Overlay.OverlayButtonWindow or Overlay.OverlayToggleWindow) continue;
            var handle = new System.Windows.Interop.WindowInteropHelper(w).Handle;
            if (handle == 0 || win32.GetRect(handle) is not { } rect) continue;
            moved.Add((w, handle, rect));
        }
        var active = moved.Select(m => m.Window).FirstOrDefault(w => w.IsActive);
        foreach (var m in moved) win32.Move(m.Handle, new Core.Windowing.PixelRect(-32000, -32000, m.Rect.Width, m.Rect.Height));
        try
        {
            var picker = new WindowScreenPicker(candidates, text);
            return picker.ShowDialog() == true ? picker.Selected : null;
        }
        finally
        {
            foreach (var m in moved) win32.Move(m.Handle, m.Rect);
            active?.Activate();
        }
    }

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
