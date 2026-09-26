using System.Globalization;
using System.Windows;
using System.Windows.Data;

namespace WindowResizer.App.Mvvm;

/// <summary>값이 매개변수와 같으면 true. 사이드바 RadioButton 의 IsChecked 에 쓴다(단방향).</summary>
public sealed class EqualsConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Equals(value, parameter);

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

/// <summary>값이 매개변수와 같으면 Visible, 아니면 Collapsed. 사이드바 페이지 전환에 쓴다.</summary>
public sealed class EqualsToVisibilityConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Equals(value, parameter) ? Visibility.Visible : Visibility.Collapsed;

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

/// <summary>bool 을 리소스 문자열 "예"/"아니오"로. 표시 언어를 따른다.</summary>
public sealed class YesNoConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Application.Current?.TryFindResource(value is true ? "Common.Yes" : "Common.No") as string
        ?? (value is true ? "Yes" : "No");

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Binding.DoNothing;
}

/// <summary>빈 대상 문자열을 리소스 "모든 창"으로.</summary>
public sealed class TargetTextConverter : IValueConverter
{
    public object Convert(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        value is string s && s.Length > 0
            ? s
            : Application.Current?.TryFindResource("Profiles.AllWindows") as string ?? "*";

    public object ConvertBack(object? value, Type targetType, object? parameter, CultureInfo culture) =>
        Binding.DoNothing;
}
