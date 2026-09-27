using System.IO;
using System.Xml.Linq;

namespace WindowResizer.App.Tests;

/// <summary>
/// 화면에 보이는 버전, <c>next/Directory.Build.props</c>, 패치노트가 같은 값인가. 셋 중 하나만 바꾸면 여기서 걸린다.
/// </summary>
[TestClass]
public sealed class VersionTests
{
    [TestMethod]
    public void Displayed_version_matches_the_props_and_the_latest_changelog_entry()
    {
        var next = FindUp("WindowResizer.slnx");
        var props = XDocument.Load(Path.Combine(next, "Directory.Build.props"));
        var declared = props.Descendants("InformationalVersion").Single().Value.Trim();

        Assert.AreEqual(declared, AppInfo.Version, "앱 어셈블리 버전이 props 와 다르다(+커밋해시가 붙었는지 확인)");
        Assert.AreEqual("v" + declared, AppInfo.DisplayVersion);

        var repo = Directory.GetParent(next)!.FullName;
        var changelog = File.ReadAllLines(Path.Combine(repo, "docs", "CHANGELOG.md"));
        var latest = changelog.First(l => l.StartsWith("## ", StringComparison.Ordinal));
        StringAssert.StartsWith(latest, "## " + declared + " ", "CHANGELOG 첫 항목이 현재 버전이 아니다: " + latest);

        foreach (var suffix in new[] { "", ".ko", ".zh-CN", ".ja" })
        {
            var note = Path.Combine(repo, "doc", "releases", $"v{declared}{suffix}.md");
            Assert.IsTrue(File.Exists(note), "패치노트가 없다: " + note);
        }
    }

    private static string FindUp(string marker)
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
            if (File.Exists(Path.Combine(dir.FullName, marker))) return dir.FullName;
        Assert.Fail(marker + " 를 찾지 못했다");
        return "";
    }
}
