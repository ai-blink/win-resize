using System.Windows;
using System.Windows.Media;
using Microsoft.Win32;

namespace WindowResizer.App.Theming;

public enum ThemeMode
{
    Light,
    Dark,
    /// <summary>Windows 고대비가 켜져 있다. 앱 색 대신 시스템 색을 쓴다(D-020).</summary>
    HighContrast,
}

/// <summary>
/// 테마 전환은 사전 교체가 아니라 브러시를 갈아 끼우는 방식이다(계획 4.7, magnifier 와 같다).
/// XAML 은 전부 <c>DynamicResource</c> 로 묶여 있어 즉시 반영된다. PyQt5 <c>theme_manager.py</c> 975줄의 대체물.
/// </summary>
public static class Theme
{
    /// <summary>토큰 이름과 (밝게, 어둡게) 값. 계획 4.7 표 그대로.</summary>
    private static readonly (string Key, string Light, string Dark)[] Tokens =
    {
        ("AppSurfaceBrush", "#F5F6F8", "#14171D"),
        ("AppPanelBrush", "#FFFFFF", "#1D222A"),
        ("AppCanvasBrush", "#F7F9FD", "#171D26"),
        ("AppBorderBrush", "#DFE3E9", "#343C47"),
        ("AppTextBrush", "#17232F", "#F1F3F6"),
        ("AppMutedTextBrush", "#65717D", "#ACB5C2"),
        ("AppHoverBrush", "#EDF0F4", "#282E38"),
        ("AppPressedBrush", "#DFE5ED", "#343C47"),
        ("AppAccentBrush", "#286BE8", "#A6C5FF"),
        ("AppAccentHoverBrush", "#1F5FCE", "#BED4FF"),
        ("AppAccentSoftBrush", "#EAF1FF", "#364662"),
        ("AppOnAccentBrush", "#FFFFFF", "#10151D"),
        ("AppDangerBrush", "#C42B1C", "#FF99A4"),
    };

    public static ThemeMode Current { get; private set; }

    /// <summary>시스템 설정을 읽는다. 고대비가 먼저다.</summary>
    public static ThemeMode DetectSystem()
    {
        if (SystemParameters.HighContrast) return ThemeMode.HighContrast;
        try
        {
            var value = Registry.GetValue(
                @"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "AppsUseLightTheme", 1);
            return value is int light && light == 0 ? ThemeMode.Dark : ThemeMode.Light;
        }
        catch (Exception)
        {
            return ThemeMode.Light;
        }
    }

    public static void Apply(ResourceDictionary resources, ThemeMode mode)
    {
        Current = mode;
        if (mode == ThemeMode.HighContrast)
        {
            ApplyHighContrast(resources);
            return;
        }

        foreach (var (key, light, dark) in Tokens)
        {
            var brush = new SolidColorBrush((Color)ColorConverter.ConvertFromString(mode == ThemeMode.Dark ? dark : light)!);
            brush.Freeze();
            resources[key] = brush;
        }
    }

    private static void ApplyHighContrast(ResourceDictionary resources)
    {
        resources["AppSurfaceBrush"] = SystemColors.WindowBrush;
        resources["AppPanelBrush"] = SystemColors.WindowBrush;
        resources["AppCanvasBrush"] = SystemColors.WindowBrush;
        resources["AppBorderBrush"] = SystemColors.WindowTextBrush;
        resources["AppTextBrush"] = SystemColors.WindowTextBrush;
        resources["AppMutedTextBrush"] = SystemColors.GrayTextBrush;
        resources["AppHoverBrush"] = SystemColors.HighlightBrush;
        resources["AppPressedBrush"] = SystemColors.HighlightBrush;
        resources["AppAccentBrush"] = SystemColors.HighlightBrush;
        resources["AppAccentHoverBrush"] = SystemColors.HotTrackBrush;
        resources["AppAccentSoftBrush"] = SystemColors.HighlightBrush;
        resources["AppOnAccentBrush"] = SystemColors.HighlightTextBrush;
        resources["AppDangerBrush"] = SystemColors.WindowTextBrush;
    }
}
