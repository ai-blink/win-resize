using System.Reflection;

namespace WindowResizer.App;

/// <summary>화면에 보이는 버전. 값은 <c>next/Directory.Build.props</c> 의 InformationalVersion 한 곳에서 온다.</summary>
public static class AppInfo
{
    public static string Version { get; } =
        typeof(AppInfo).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion ?? "?";

    public static string DisplayVersion => "v" + Version;
}
