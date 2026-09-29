using System.Windows;

namespace WindowResizer.App;

/// <summary>
/// 앱 아이콘. 파일 하나(<c>Assets/app.ico</c>, 16-256 px 아홉 크기)를 exe 아이콘, 창 제목줄, 트레이가 함께 쓴다.
/// 트레이(WinForms <c>NotifyIcon</c>)는 WPF 이미지를 받지 못하므로 같은 리소스를 GDI 아이콘으로 읽는다.
/// </summary>
public static class AppIcon
{
    public static Uri Uri { get; } = new("pack://application:,,,/WindowResizer.App;component/Assets/app.ico");

    /// <summary>GDI 아이콘. <paramref name="size"/> 에 가장 가까운 프레임을 고른다. 부른 쪽이 <c>Dispose</c> 한다.</summary>
    public static System.Drawing.Icon Load(System.Drawing.Size size)
    {
        var resource = Application.GetResourceStream(Uri)
            ?? throw new InvalidOperationException("앱 아이콘 리소스를 찾지 못했다: " + Uri);
        using var stream = resource.Stream;
        return new System.Drawing.Icon(stream, size);
    }
}
