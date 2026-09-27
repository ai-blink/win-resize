using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Tests;

/// <summary>문서 편집 연산(S4b). 파일 입출력 없이 문서만 잰다.</summary>
[TestClass]
public sealed class ProfileDocumentEditingTests
{
    [TestMethod]
    public void Add_gives_a_16_hex_id_stamps_times_and_never_reuses_an_id()
    {
        var doc = new ProfileDocument();

        var first = doc.Add(new Profile { Name = "Blender" }, 1000.5);
        var second = doc.Add(new Profile { Name = "Blender", CreatedAt = 1000.5 }, 1000.5);

        StringAssert.Matches(first, new System.Text.RegularExpressions.Regex("^[0-9a-f]{16}$"));
        Assert.AreNotEqual(first, second, "같은 이름, 같은 시각이어도 ID 가 겹치면 안 된다");
        Assert.AreEqual((1000.5, 1000.5), (doc.Find(first)!.CreatedAt, doc.Find(first)!.ModifiedAt));
    }

    [TestMethod]
    public void Replace_keeps_the_order_and_remove_drops_only_that_profile()
    {
        var doc = new ProfileDocument();
        var a = doc.Add(new Profile { Name = "a" }, 1);
        var b = doc.Add(new Profile { Name = "b" }, 1);
        var c = doc.Add(new Profile { Name = "c" }, 1);

        Assert.IsTrue(doc.Replace(b, new Profile { Name = "b2" }, 5));
        Assert.IsFalse(doc.Replace("missing", new Profile { Name = "x" }, 5));
        CollectionAssert.AreEqual(new[] { "a", "b2", "c" }, doc.Profiles.Select(p => p.Value.Name).ToArray());
        Assert.AreEqual(5, doc.Find(b)!.ModifiedAt);

        Assert.IsTrue(doc.Remove(a));
        CollectionAssert.AreEqual(new[] { b, c }, doc.Profiles.Select(p => p.Key).ToArray());
    }

    [TestMethod]
    public void Unique_name_appends_a_number_ignoring_case_and_skips_the_profile_being_edited()
    {
        var doc = new ProfileDocument();
        var id = doc.Add(new Profile { Name = "Blender" }, 1);
        doc.Add(new Profile { Name = "blender (2)" }, 1);

        Assert.AreEqual("Notepad", doc.UniqueName("Notepad"));
        Assert.AreEqual("Blender (3)", doc.UniqueName("Blender"));
        Assert.AreEqual("Blender", doc.UniqueName("Blender", exceptId: id));
    }

    [TestMethod]
    public void Record_applied_counts_windows_and_ignores_zero()
    {
        var profile = new Profile();

        profile.RecordApplied(0, 10);
        Assert.AreEqual((0, (double?)null), (profile.AppliedCount, profile.LastAppliedAt));

        profile.RecordApplied(3, 20);
        Assert.AreEqual((3, (double?)20), (profile.AppliedCount, profile.LastAppliedAt));
    }

    [TestMethod]
    public void From_window_matches_by_path_when_known_and_by_process_otherwise()
    {
        var config = new WindowConfiguration { Width = 10, Height = 10 };

        var byPath = Profile.FromWindow(new WindowInfo("t", "blender.exe", "", @"C:\B\blender.exe"), config, "Blender");
        Assert.AreEqual(MatchingStrategy.ExecutablePath, byPath.MatchingCriteria!.Strategy);
        Assert.IsTrue(byPath.Matches(new WindowInfo("other title", "blender.exe", "", @"c:\b\BLENDER.exe")));

        var elevated = Profile.FromWindow(new WindowInfo("t", "taskmgr.exe"), config, "Taskmgr");
        Assert.AreEqual(MatchingStrategy.ProcessName, elevated.MatchingCriteria!.Strategy);
        Assert.AreEqual("taskmgr.exe", elevated.MatchingCriteria.ProcessNamePattern);
    }

    [TestMethod]
    public void Program_name_comes_from_the_executable_not_the_title()
    {
        Assert.AreEqual("Blender", Profile.ProgramName(new WindowInfo("* (Unsaved) - Blender 5.2.0 LTS", "blender.exe")));
        Assert.AreEqual("Untitled", Profile.ProgramName(new WindowInfo(" Untitled ", "")));
    }

    [TestMethod]
    public void Clone_is_deep_and_keeps_unknown_keys()
    {
        var original = new Profile
        {
            Name = "a",
            WindowConfig = new WindowConfiguration { Width = 1, Height = 1 },
            Extra = new() { ["future"] = System.Text.Json.JsonDocument.Parse("\"x\"").RootElement },
        };

        var copy = ProfileJson.Clone(original);
        copy.WindowConfig!.Width = 99;

        Assert.AreEqual(1, original.WindowConfig.Width);
        Assert.IsTrue(copy.Extra!.ContainsKey("future"));
    }
}
