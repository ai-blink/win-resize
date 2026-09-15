using System.Linq;
using System.Reflection;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 의존은 Core &lt;- Infrastructure 한 방향이다.
///
/// "참조한다"는 쪽은 프로젝트 파일로 재야 한다(App.Tests 참조 - 컴파일러가
/// 쓰이지 않는 참조를 산출물에서 뺀다). 여기서는 "참조하지 않는다"는 쪽,
/// 즉 되돌아오는 화살표가 없다는 것만 어셈블리로 확인한다.
/// </summary>
[TestClass]
public sealed class ProjectWiringTests
{
    [TestMethod]
    public void Core_does_not_reference_infrastructure()
    {
        var referenced = WindowResizer.Core.CoreAssembly.Reference
            .GetReferencedAssemblies()
            .Select(name => name.Name)
            .ToArray();

        CollectionAssert.DoesNotContain(
            referenced,
            "WindowResizer.Infrastructure",
            "Core 가 Infrastructure 를 참조한다. 의존은 한 방향이어야 한다.");
    }

    /// <summary>
    /// 플랫폼은 <c>TargetFrameworkAttribute</c> 가 아니라 <c>TargetPlatformAttribute</c> 에 있다.
    /// net10.0 과 net10.0-windows 의 FrameworkName 은 똑같이 ".NETCoreApp,Version=v10.0" 이다
    /// (2026-09-16 실측).
    /// </summary>
    [TestMethod]
    public void Infrastructure_targets_windows()
    {
        var platform = WindowResizer.Infrastructure.InfrastructureAssembly.Reference
            .GetCustomAttribute<System.Runtime.Versioning.TargetPlatformAttribute>()
            ?.PlatformName ?? string.Empty;

        StringAssert.Contains(
            platform,
            "Windows",
            System.StringComparison.OrdinalIgnoreCase,
            "Infrastructure 가 Windows 전용 framework 를 target 하지 않는다: '" + platform +
            "'. Win32 P/Invoke 가 여기 살아야 하므로 net10.0-windows 여야 한다.");
    }
}
