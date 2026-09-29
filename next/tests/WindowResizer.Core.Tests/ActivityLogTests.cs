using WindowResizer.Core.Diagnostics;

namespace WindowResizer.Core.Tests;

/// <summary>로그 페이지의 기록: 쌓기, 최대 개수, 걸러 보기, 내보내기 본문.</summary>
[TestClass]
public sealed class ActivityLogTests
{
    private static readonly DateTime At = new(2026, 9, 30, 14, 3, 22);

    private static ActivityLog Log() => new(() => At);

    [TestMethod]
    public void An_entry_keeps_its_time_level_and_text_and_formats_like_the_pyqt5_debug_window()
    {
        var log = Log();

        var entry = log.Add(LogLevel.Warning, "저장하지 못했습니다");

        Assert.AreEqual(At, entry.Time);
        Assert.AreEqual("[14:03:22] WARNING: 저장하지 못했습니다", entry.Format());
        Assert.HasCount(1, log.Entries);
    }

    [TestMethod]
    public void Only_the_newest_entries_are_kept_when_the_maximum_is_exceeded()
    {
        var log = Log();
        var trimmed = 0;
        log.Trimmed += () => trimmed++;
        log.MaxEntries = 100;

        for (var i = 0; i < 105; i++) log.Add(LogLevel.Info, "line " + i);

        Assert.HasCount(100, log.Entries);
        Assert.AreEqual("line 5", log.Entries[0].Message, "가장 오래된 다섯 줄이 버려진다");
        Assert.AreEqual("line 104", log.Entries[^1].Message);
        Assert.AreEqual(5, trimmed);
    }

    [TestMethod]
    [DataRow(50, 100)]
    [DataRow(100, 100)]
    [DataRow(1000, 1000)]
    [DataRow(99999, 10000)]
    public void The_maximum_is_kept_between_100_and_10000(int asked, int expected)
    {
        var log = Log();

        log.MaxEntries = asked;

        Assert.AreEqual(expected, log.MaxEntries);
    }

    [TestMethod]
    public void Lowering_the_maximum_drops_the_oldest_entries_at_once()
    {
        var log = Log();
        for (var i = 0; i < 300; i++) log.Add(LogLevel.Info, "line " + i);
        var trimmed = false;
        log.Trimmed += () => trimmed = true;

        log.MaxEntries = 100;

        Assert.HasCount(100, log.Entries);
        Assert.AreEqual("line 200", log.Entries[0].Message);
        Assert.IsTrue(trimmed);
    }

    [TestMethod]
    public void At_least_returns_the_given_level_and_worse_in_order()
    {
        var log = Log();
        log.Add(LogLevel.Info, "a");
        log.Add(LogLevel.Error, "b");
        log.Add(LogLevel.Warning, "c");

        CollectionAssert.AreEqual(new[] { "a", "b", "c" }, log.AtLeast(LogLevel.Info).Select(e => e.Message).ToArray());
        CollectionAssert.AreEqual(new[] { "b", "c" }, log.AtLeast(LogLevel.Warning).Select(e => e.Message).ToArray());
        CollectionAssert.AreEqual(new[] { "b" }, log.AtLeast(LogLevel.Error).Select(e => e.Message).ToArray());
    }

    [TestMethod]
    public void Text_and_export_give_only_the_filtered_lines_and_the_export_has_a_header()
    {
        var log = Log();
        log.Add(LogLevel.Info, "quiet");
        log.Add(LogLevel.Error, "boom");

        Assert.AreEqual("[14:03:22] ERROR: boom", log.Text(LogLevel.Warning));

        var export = log.ExportText(LogLevel.Warning, "WindowResizer log", "Generated");
        StringAssert.StartsWith(export, "WindowResizer log");
        StringAssert.Contains(export, "Generated: 2026-09-30 14:03:22");
        StringAssert.Contains(export, "[14:03:22] ERROR: boom");
        Assert.DoesNotContain("quiet", export);
    }

    [TestMethod]
    public void Clearing_announces_once_and_an_empty_log_announces_nothing()
    {
        var log = Log();
        var cleared = 0;
        log.Cleared += () => cleared++;

        log.Clear();
        Assert.AreEqual(0, cleared);

        log.Add(LogLevel.Info, "x");
        log.Clear();
        Assert.AreEqual(1, cleared);
        Assert.IsEmpty(log.Entries);
    }
}
