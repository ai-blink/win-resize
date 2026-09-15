using System.Linq;
using System.Reflection;

namespace WindowResizer.Core.Tests;

/// <summary>
/// Core 는 어떤 Windows 전용 표면에도 기대지 않는다.
///
/// 1차 방어선은 컴파일러다. Core 가 net10.0(-windows 없음)을 target 하므로
/// WPF 타입을 쓰면 CS0246 으로 빌드가 깨진다. 2026-09-16 실측으로 확인했다.
///
/// 이 테스트는 그 방어선이 조용히 풀리는 경우를 잡는다. 누군가 Core 의
/// TargetFramework 에 -windows 를 붙이거나, Windows 전용 패키지를 참조로
/// 끌어오면 빌드는 통과하고 경계만 사라진다. 그때 여기서 실패한다.
/// </summary>
[TestClass]
public sealed class LayerBoundaryTests
{
    /// <summary>Core 에 들어오면 안 되는 어셈블리 이름 조각.</summary>
    private static readonly string[] ForbiddenAssemblyMarkers =
    {
        "PresentationCore",
        "PresentationFramework",
        "WindowsBase",
        "System.Windows.Forms",
        "System.Drawing.Common",
    };

    private static Assembly CoreAssembly => WindowResizer.Core.CoreAssembly.Reference;

    [TestMethod]
    public void Core_does_not_reference_any_windows_only_assembly()
    {
        var referenced = CoreAssembly.GetReferencedAssemblies()
            .Select(name => name.Name ?? string.Empty)
            .ToArray();

        var offenders = referenced
            .Where(name => ForbiddenAssemblyMarkers.Any(
                marker => name.Contains(marker, System.StringComparison.OrdinalIgnoreCase)))
            .ToArray();

        Assert.IsEmpty(
            offenders,
            "Core 가 Windows 전용 어셈블리를 참조한다: " + string.Join(", ", offenders) +
            ". Win32 와 WPF 는 Infrastructure 와 App 이 소유한다.");
    }

    /// <summary>
    /// OS 접미사는 <c>TargetFrameworkAttribute</c> 에 없다. net10.0 과 net10.0-windows 는
    /// 둘 다 ".NETCoreApp,Version=v10.0" 을 돌려준다(2026-09-16 실측). 플랫폼은
    /// <c>TargetPlatformAttribute</c> 가 들고 있고, 플랫폼 중립 대상에는 그 속성이 아예 없다.
    /// 이걸 모르고 FrameworkName 으로 재면 Core 를 -windows 로 바꿔도 통과하는
    /// 거짓 통과가 된다.
    /// </summary>
    [TestMethod]
    public void Core_targets_a_platform_neutral_framework()
    {
        var platform = CoreAssembly
            .GetCustomAttribute<System.Runtime.Versioning.TargetPlatformAttribute>()
            ?.PlatformName;

        Assert.IsNull(
            platform,
            "Core 가 플랫폼 전용 framework 를 target 한다: " + platform +
            ". net10.0 으로 되돌려 계층 경계를 빌드가 지키게 해야 한다.");
    }
}
