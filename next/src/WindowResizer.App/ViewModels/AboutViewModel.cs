using WindowResizer.App.Mvvm;
using WindowResizer.Core.Diagnostics;

namespace WindowResizer.App.ViewModels;

/// <summary>
/// 정보 페이지에 보이는 값. "지금 이 앱이 어디를 읽고 쓰는가"를 보여 주는 것이 목적이다 - 사본으로 시험할 때
/// 실제 프로필 폴더나 실제 설정 키를 건드리지 않는지 눈으로 확인할 수 있다. 조립은 <c>App.xaml.cs</c> 가 한다.
/// </summary>
/// <param name="Version">화면에 보이는 버전(<c>v0.02.0-preview.4</c>).</param>
/// <param name="Runtime">실행 중인 .NET 이름과 버전.</param>
/// <param name="IsAdministrator">관리자 권한으로 실행 중인가. 아니면 관리자 창은 옮길 수 없다.</param>
/// <param name="SettingsKey">HKCU 아래 앱 설정 키(<c>HKCU\</c> 는 뺀 경로).</param>
public sealed record AboutInfo(
    string Version, string Runtime, bool IsAdministrator, string ExecutablePath, string ProfilesFolder,
    string SettingsKey, string OverlayKey, string HotkeyKey)
{
    public static AboutInfo Unknown { get; } = new("?", "", false, "", "", "", "", "");
}

/// <summary>정보 페이지: 값 보이기, 프로필 폴더 열기, 정보와 설정 키 경로 복사.</summary>
public sealed class AboutViewModel : ObservableObject
{
    private readonly IDialogService? _dialogs;
    private readonly Func<string, string> _text;
    private readonly Action<string, LogLevel> _status;

    public AboutViewModel(AboutInfo info, IDialogService? dialogs, Func<string, string> text, Action<string, LogLevel> status)
    {
        Info = info;
        _dialogs = dialogs;
        _text = text;
        _status = status;
        OpenProfilesFolderCommand = new RelayCommand(OpenProfilesFolder, () => Info.ProfilesFolder.Length > 0);
        CopyInfoCommand = new RelayCommand(() => Copy(InfoText(), "Status.InfoCopied"));
        CopySettingsKeyCommand = new RelayCommand(() => Copy(SettingsKeyPath, "Status.KeyCopied"), () => Info.SettingsKey.Length > 0);
    }

    public AboutInfo Info { get; }

    public System.Windows.Input.ICommand OpenProfilesFolderCommand { get; }
    public System.Windows.Input.ICommand CopyInfoCommand { get; }
    public System.Windows.Input.ICommand CopySettingsKeyCommand { get; }

    public string AdministratorText => _text(Info.IsAdministrator ? "About.Yes" : "About.No");

    public string SettingsKeyPath => Registry(Info.SettingsKey);
    public string OverlayKeyPath => Registry(Info.OverlayKey);
    public string HotkeyKeyPath => Registry(Info.HotkeyKey);

    /// <summary>표시 언어가 바뀌었다 - 예/아니오 문구를 다시 읽게 한다.</summary>
    public void RefreshTexts() => OnPropertyChanged(nameof(AdministratorText));

    /// <summary>버그를 알릴 때 그대로 붙여 넣을 수 있는 여러 줄 본문.</summary>
    public string InfoText() => string.Join(Environment.NewLine,
        $"WindowResizer {Info.Version}",
        $"{_text("About.Runtime")}: {Info.Runtime}",
        $"{_text("About.Administrator")}: {AdministratorText}",
        $"{_text("About.Executable")}: {Info.ExecutablePath}",
        $"{_text("About.ProfilesFolder")}: {Info.ProfilesFolder}",
        $"{_text("About.SettingsKey")}: {SettingsKeyPath}",
        $"{_text("About.OverlayKey")}: {OverlayKeyPath}",
        $"{_text("About.HotkeyKey")}: {HotkeyKeyPath}");

    private static string Registry(string key) => key.Length == 0 ? "" : @"HKCU\" + key;

    private void OpenProfilesFolder()
    {
        var error = _dialogs?.OpenFolder(Info.ProfilesFolder);
        if (error is not null) _status(string.Format(_text("Status.FolderOpenFailed"), error), LogLevel.Warning);
    }

    private void Copy(string text, string doneKey)
    {
        var copied = _dialogs?.CopyToClipboard(text) ?? false;
        _status(_text(copied ? doneKey : "Status.CopyFailed"), copied ? LogLevel.Info : LogLevel.Warning);
    }
}
