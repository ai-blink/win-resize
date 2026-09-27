using System.Windows;
using WindowResizer.App.Theming;
using WindowResizer.App.ViewModels;
using WindowResizer.Infrastructure.Persistence;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.App;

/// <summary>
/// 조합 루트. Core 와 Infrastructure 부품을 여기서만 엮는다.
///
/// 실행 인자:
///   <c>--profiles-dir &lt;폴더&gt;</c>  프로필 폴더를 바꾼다. 기본은 실행 파일 옆 <c>profiles</c>(D-019).
///   개발 빌드는 <c>next\...\bin</c> 에서 뜨므로, 실사용 프로필을 보려면 <c>C:\app\profiles</c> 를 넘긴다.
///   S4b 부터 이 폴더에 <b>쓴다</b>(적용 횟수, 편집, 삭제). 개발 중에는 실사용 폴더가 아니라 사본을 넘긴다.
/// </summary>
public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        // 이전 실행이 커서를 가둔 채 죽었으면 푼다(S3c 실측: Windows 는 풀어 주지 않는다).
        CursorClip.ReleaseStale();

        Theme.Apply(Resources, Theme.DetectSystem());

        var store = new ProfileStore(ProfilesDirectory(e.Args));
        var loaded = store.Load();
        var windows = new Win32Windows();

        var viewModel = new MainViewModel(
            () => windows.EnumerateUserWindows()
                .Select(w => new WindowRow(w.Handle, w.Info, w.ProcessId, w.Rect, w.IsMaximized, w.IsMinimized))
                .ToList(),
            windows,
            loaded.Document,
            document => Save(store, loaded.Source, document),
            new DialogService(Text),
            Text,
            Shutdown);

        viewModel.RefreshWindows();
        var notice = LoadNotice(loaded);
        if (notice is not null) viewModel.ShowStatus(notice);

        MainWindow = new MainWindow { DataContext = viewModel };
        MainWindow.Show();
    }

    private string Text(string key) => TryFindResource(key) as string ?? key;

    /// <summary>
    /// 본 파일과 백업을 둘 다 못 읽었으면 쓰지 않는다. 빈 문서를 저장하면 사용자의 깨진(그러나 고칠 수 있는)
    /// 파일이 빈 파일로 바뀌고, 백업마저 그 깨진 파일로 밀린다.
    /// </summary>
    private string? Save(ProfileStore store, ProfileSource source, Core.Profiles.ProfileDocument document)
    {
        if (source == ProfileSource.Unreadable) return Text("Status.ReadOnlyProfiles");
        return store.TrySave(document, out var error) ? null : error!.Message;
    }

    private string? LoadNotice(ProfileStoreLoad loaded) => loaded.Source switch
    {
        ProfileSource.Backup => Text("Status.ProfilesFromBackup"),
        ProfileSource.Unreadable => string.Format(Text("Status.ProfilesUnreadable"), string.Join("; ", loaded.FileErrors)),
        _ when loaded.ProfileErrors.Count > 0 => string.Format(Text("Status.ProfilesSkipped"), loaded.ProfileErrors.Count),
        _ => null,
    };

    private static string ProfilesDirectory(string[] args)
    {
        var index = Array.IndexOf(args, "--profiles-dir");
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : ProfileStore.DefaultDirectory;
    }
}
