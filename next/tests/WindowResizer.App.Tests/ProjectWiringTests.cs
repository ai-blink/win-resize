using System;
using System.IO;
using System.Linq;

namespace WindowResizer.App.Tests;

/// <summary>
/// App 은 Core 와 Infrastructure 를 모두 참조하는 조합 루트다.
/// 반대로 두 계층 중 어느 쪽도 App 을 알아서는 안 된다.
///
/// 참조 방향을 두 가지 방법으로 잰다.
///
/// 위쪽 방향(App -> 계층)은 **프로젝트 파일**을 읽는다. 어셈블리 메타데이터로는
/// 잴 수 없다 - C# 컴파일러는 실제로 쓰이지 않는 참조를 산출물에서 빼기 때문에,
/// 아직 Core 타입을 쓰지 않는 지금은 ProjectReference 가 있어도
/// GetReferencedAssemblies() 에 나타나지 않는다. 2026-09-16 실측으로 확인했다.
///
/// 아래쪽 방향(계층 -> App)은 어셈블리로 잰다. 이쪽은 "없어야 한다"는 주장이고,
/// 컴파일러가 참조를 빼는 성질은 거짓 통과가 아니라 더 강한 보장이 된다.
/// </summary>
[TestClass]
public sealed class ProjectWiringTests
{
    private static string RepoNextRoot()
    {
        var dir = new DirectoryInfo(AppContext.BaseDirectory);
        while (dir is not null && !File.Exists(Path.Combine(dir.FullName, "WindowResizer.slnx")))
        {
            dir = dir.Parent;
        }

        Assert.IsNotNull(dir, "WindowResizer.slnx 를 상위 경로에서 찾지 못했다.");
        return dir!.FullName;
    }

    private static string[] ProjectReferencesOf(string projectRelativePath)
    {
        var path = Path.Combine(RepoNextRoot(), projectRelativePath);
        Assert.IsTrue(File.Exists(path), "프로젝트 파일이 없다: " + path);

        return File.ReadAllLines(path)
            .Where(line => line.Contains("ProjectReference", StringComparison.Ordinal))
            .ToArray();
    }

    private static string[] AssemblyReferencesOf(System.Reflection.Assembly assembly) =>
        assembly.GetReferencedAssemblies()
            .Select(name => name.Name ?? string.Empty)
            .ToArray();

    [TestMethod]
    public void App_project_references_both_lower_layers()
    {
        var references = ProjectReferencesOf(
            Path.Combine("src", "WindowResizer.App", "WindowResizer.App.csproj"));

        Assert.IsTrue(
            references.Any(line => line.Contains("WindowResizer.Core.csproj", StringComparison.Ordinal)),
            "App 이 Core 를 참조하지 않는다.");
        Assert.IsTrue(
            references.Any(line => line.Contains("WindowResizer.Infrastructure.csproj", StringComparison.Ordinal)),
            "App 이 Infrastructure 를 참조하지 않는다.");
    }

    [TestMethod]
    public void Infrastructure_project_references_core()
    {
        var references = ProjectReferencesOf(
            Path.Combine("src", "WindowResizer.Infrastructure", "WindowResizer.Infrastructure.csproj"));

        Assert.IsTrue(
            references.Any(line => line.Contains("WindowResizer.Core.csproj", StringComparison.Ordinal)),
            "Infrastructure 가 Core 를 참조하지 않는다.");
    }

    [TestMethod]
    public void Core_project_references_nothing_of_ours()
    {
        var references = ProjectReferencesOf(
            Path.Combine("src", "WindowResizer.Core", "WindowResizer.Core.csproj"));

        Assert.IsEmpty(
            references,
            "Core 가 다른 프로젝트를 참조한다. Core 는 아무것도 참조하지 않아야 한다: "
            + string.Join(" / ", references));
    }

    /// <summary>
    /// WinForms 는 트레이 아이콘 하나 때문에 켰다(S4c). 다른 파일로 번지면 WPF 와 이름이 겹치고
    /// 두 UI 프레임워크가 섞인다 - <c>TrayIcon.cs</c> 한 곳으로 묶어 둔다.
    /// </summary>
    [TestMethod]
    public void WinForms_is_used_only_by_the_tray_icon()
    {
        var appDir = Path.Combine(RepoNextRoot(), "src", "WindowResizer.App");
        var offenders = Directory.EnumerateFiles(appDir, "*.cs", SearchOption.AllDirectories)
            .Where(f => !f.Contains(Path.DirectorySeparatorChar + "obj" + Path.DirectorySeparatorChar)
                     && !f.Contains(Path.DirectorySeparatorChar + "bin" + Path.DirectorySeparatorChar))
            .Where(f => Path.GetFileName(f) != "TrayIcon.cs")
            .Where(f => File.ReadAllText(f).Contains("System.Windows.Forms", StringComparison.Ordinal))
            .Select(Path.GetFileName)
            .ToList();

        Assert.IsEmpty(offenders, "WinForms 를 쓰는 파일: " + string.Join(", ", offenders));
    }

    [TestMethod]
    public void Lower_layers_do_not_reference_app()
    {
        CollectionAssert.DoesNotContain(
            AssemblyReferencesOf(WindowResizer.Core.CoreAssembly.Reference),
            "WindowResizer.App",
            "Core 가 App 을 참조한다.");

        CollectionAssert.DoesNotContain(
            AssemblyReferencesOf(WindowResizer.Infrastructure.InfrastructureAssembly.Reference),
            "WindowResizer.App",
            "Infrastructure 가 App 을 참조한다.");
    }
}
