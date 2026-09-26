using System.Text;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Infrastructure.Persistence;

/// <summary>어느 파일에서 읽었는가.</summary>
public enum ProfileSource
{
    /// <summary>본 파일도 백업도 없다. 첫 실행이다.</summary>
    None,
    Primary,
    /// <summary>본 파일이 깨져 백업에서 되살렸다.</summary>
    Backup,
    /// <summary>둘 다 있었지만 둘 다 읽지 못했다.</summary>
    Unreadable,
}

public sealed record ProfileStoreLoad(
    ProfileSource Source,
    ProfileDocument Document,
    IReadOnlyList<ProfileLoadError> ProfileErrors,
    IReadOnlyList<string> FileErrors);

/// <summary>
/// profiles.json 의 파일 입출력. 순서는 PyQt5 <c>ProfileManager.save_profiles</c> / <c>load_profiles</c> 와 같다.
///
/// 저장: <c>.json.tmp</c> 에 쓰고 디스크까지 flush -> 기존 본 파일을 <c>.json.backup</c> 으로 복사 ->
/// tmp 를 본 파일 자리로 교체. 어느 단계에서 실패해도 본 파일은 이전 내용 그대로다.
/// 읽기: 본 파일 -> 실패하면 백업. 파일 전체를 못 읽을 때만 백업으로 넘어가고,
/// 프로필 하나가 깨진 것은 <see cref="ProfileJson.Parse"/> 가 그 프로필만 건너뛴다.
/// </summary>
public sealed class ProfileStore
{
    public const string FileName = "profiles.json";

    private readonly TimeProvider _clock;

    public ProfileStore(string directory, TimeProvider? clock = null)
    {
        Directory = directory;
        _clock = clock ?? TimeProvider.System;
    }

    /// <summary>
    /// 저장 경로 규칙(D-019): <b>실행 파일 폴더 아래 <c>profiles</c></b>.
    /// PyQt5 는 작업 폴더 기준 상대경로 <c>Path("profiles")</c> 였고, 어디서 실행했느냐에 따라
    /// 프로필 세트가 여러 벌로 갈렸다. 실행 파일 기준이면 실행 위치와 무관하고, 배포 위치
    /// <c>C:\app\WindowResizer.exe</c> 에서는 PyQt5 가 쓰던 <c>C:\app\profiles</c> 와 같은 파일이다.
    /// </summary>
    public static string DefaultDirectory => Path.Combine(AppContext.BaseDirectory, "profiles");

    public string Directory { get; }
    public string FilePath => Path.Combine(Directory, FileName);
    public string BackupPath => FilePath + ".backup";
    public string TemporaryPath => FilePath + ".tmp";

    public ProfileStoreLoad Load()
    {
        var fileErrors = new List<string>();
        var candidates = new[] { (FilePath, ProfileSource.Primary), (BackupPath, ProfileSource.Backup) };

        if (!candidates.Any(c => File.Exists(c.Item1)))
            return new ProfileStoreLoad(ProfileSource.None, new ProfileDocument(), [], fileErrors);

        foreach (var (path, source) in candidates)
        {
            if (!File.Exists(path)) continue;
            try
            {
                var result = ProfileJson.Parse(File.ReadAllText(path, Encoding.UTF8));
                return new ProfileStoreLoad(source, result.Document, result.Errors, fileErrors);
            }
            catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Text.Json.JsonException)
            {
                fileErrors.Add(path + ": " + ex.Message);
            }
        }

        return new ProfileStoreLoad(ProfileSource.Unreadable, new ProfileDocument(), [], fileErrors);
    }

    /// <summary>
    /// 원자적으로 저장한다. PyQt5 와 같이 파일의 <c>created_at</c> 을 저장 시각으로 찍는다.
    /// 실패하면 false 와 원인을 돌려주고 본 파일은 건드리지 않은 상태다.
    /// </summary>
    public bool TrySave(ProfileDocument document, out Exception? error)
    {
        error = null;
        try
        {
            System.IO.Directory.CreateDirectory(Directory);
            document.CreatedAt = _clock.GetUtcNow().ToUnixTimeMilliseconds() / 1000.0;

            // BOM 없는 UTF-8. BOM 이 붙으면 PyQt5 의 json.load 가 실패한다.
            var bytes = new UTF8Encoding(false).GetBytes(ProfileJson.Serialize(document));
            using (var stream = new FileStream(TemporaryPath, FileMode.Create, FileAccess.Write, FileShare.None))
            {
                stream.Write(bytes);
                stream.Flush(flushToDisk: true);
            }

            // 교체 직전의 정상 파일을 남긴다.
            if (File.Exists(FilePath))
                File.Copy(FilePath, BackupPath, overwrite: true);

            File.Move(TemporaryPath, FilePath, overwrite: true);
            return true;
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException)
        {
            error = ex;
            return false;
        }
        finally
        {
            try
            {
                if (File.Exists(TemporaryPath)) File.Delete(TemporaryPath);
            }
            catch (IOException)
            {
                // 남은 tmp 는 다음 저장이 덮어쓴다.
            }
        }
    }
}
