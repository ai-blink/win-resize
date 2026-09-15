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
