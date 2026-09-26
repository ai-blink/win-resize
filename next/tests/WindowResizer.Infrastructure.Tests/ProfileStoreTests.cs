using System.Text;
using WindowResizer.Core.Profiles;
using WindowResizer.Infrastructure.Persistence;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// profiles.json 파일 입출력. PyQt5 에서 옮긴 것은 원래 테스트 이름을 주석에 남긴다.
/// 모든 테스트는 임시 폴더에서만 쓴다. 실사용 파일은 복사본으로만 읽는다.
/// </summary>
[TestClass]
public sealed class ProfileStoreTests
{
    private string _dir = "";

    [TestInitialize]
    public void CreateDirectory()
    {
        _dir = Path.Combine(Path.GetTempPath(), "wr-store-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(_dir);
    }

    [TestCleanup]
    public void DeleteDirectory() => Directory.Delete(_dir, recursive: true);

    [TestMethod]
    public void Save_then_load_returns_the_same_profiles_and_stamps_created_at()
    {
        var store = new ProfileStore(_dir, new FixedClock(DateTimeOffset.FromUnixTimeSeconds(1_790_000_000)));

        Assert.IsTrue(store.TrySave(Document("블렌더"), out var error), error?.Message);
        var loaded = store.Load();

        Assert.AreEqual(ProfileSource.Primary, loaded.Source);
        Assert.AreEqual("블렌더", loaded.Document.Profiles.Single().Value.Name);
        Assert.AreEqual(1_790_000_000.0, loaded.Document.CreatedAt);
        Assert.AreNotEqual(0xEF, File.ReadAllBytes(store.FilePath)[0], "BOM 이 붙으면 PyQt5 json.load 가 실패한다");
        Assert.IsFalse(File.Exists(store.TemporaryPath));
    }

    [TestMethod]
    public void Second_save_keeps_the_previous_file_as_backup()
    {
        var store = new ProfileStore(_dir);
        store.TrySave(Document("처음"), out _);
        store.TrySave(Document("나중"), out _);

        var backup = ProfileJson.Parse(File.ReadAllText(store.BackupPath, Encoding.UTF8));

        Assert.AreEqual("처음", backup.Document.Profiles.Single().Value.Name);
        Assert.AreEqual("나중", store.Load().Document.Profiles.Single().Value.Name);
    }

    // tests/test_review_hardening.py
    //   test_failed_save_preserves_primary_file_and_backup_recovers (앞부분)
    [TestMethod]
    public void Failed_save_leaves_the_primary_file_untouched()
    {
        var store = new ProfileStore(_dir);
        store.TrySave(Document("원본"), out _);
        var before = File.ReadAllBytes(store.FilePath);

        // tmp 자리에 폴더를 두어 쓰기를 실패시킨다.
        Directory.CreateDirectory(store.TemporaryPath);
        var saved = store.TrySave(Document("덮어쓰기"), out var error);
        Directory.Delete(store.TemporaryPath);

        Assert.IsFalse(saved);
        Assert.IsNotNull(error);
        CollectionAssert.AreEqual(before, File.ReadAllBytes(store.FilePath));
    }

    // tests/test_review_hardening.py
    //   test_failed_save_preserves_primary_file_and_backup_recovers (뒷부분)
    [TestMethod]
    public void Corrupt_primary_file_is_recovered_from_backup()
    {
        var store = new ProfileStore(_dir);
        store.TrySave(Document("백업될 것"), out _);
        File.Copy(store.FilePath, store.BackupPath, overwrite: true);
        File.WriteAllText(store.FilePath, "{invalid json");

        var loaded = store.Load();

        Assert.AreEqual(ProfileSource.Backup, loaded.Source);
        Assert.AreEqual("백업될 것", loaded.Document.Profiles.Single().Value.Name);
        Assert.HasCount(1, loaded.FileErrors);
    }

    [TestMethod]
    public void No_files_means_first_run()
    {
        var loaded = new ProfileStore(_dir).Load();

        Assert.AreEqual(ProfileSource.None, loaded.Source);
        Assert.IsEmpty(loaded.Document.Profiles);
    }

    [TestMethod]
    public void Both_files_corrupt_is_reported_not_silently_empty()
    {
        var store = new ProfileStore(_dir);
        File.WriteAllText(store.FilePath, "{");
        File.WriteAllText(store.BackupPath, "[");

        var loaded = store.Load();

        Assert.AreEqual(ProfileSource.Unreadable, loaded.Source);
        Assert.HasCount(2, loaded.FileErrors);
    }

    [TestMethod]
    public void Default_directory_is_next_to_the_executable_not_the_working_directory()
    {
        var expected = Path.Combine(AppContext.BaseDirectory, "profiles");

        Assert.AreEqual(expected, ProfileStore.DefaultDirectory);
        Assert.IsTrue(Path.IsPathRooted(ProfileStore.DefaultDirectory));
    }

    [TestMethod]
    [TestCategory("Gate")]
    public void Real_profiles_copy_loads_from_the_primary_file_without_errors()
    {
        const string real = @"C:\app\profiles\profiles.json";
        if (!File.Exists(real)) Assert.Inconclusive("실사용 프로필 파일이 없다: " + real);

        File.Copy(real, Path.Combine(_dir, ProfileStore.FileName));
        var loaded = new ProfileStore(_dir).Load();

        Assert.AreEqual(ProfileSource.Primary, loaded.Source);
        Assert.IsEmpty(loaded.ProfileErrors);
        Assert.IsNotEmpty(loaded.Document.Profiles);
    }

    private static ProfileDocument Document(string name)
    {
        var document = new ProfileDocument();
        document.Profiles.Add(new("id-" + name, new Profile { Name = name }));
        return document;
    }

    private sealed class FixedClock(DateTimeOffset now) : TimeProvider
    {
        public override DateTimeOffset GetUtcNow() => now;
    }
}
