using System.Globalization;

namespace WindowResizer.Core.Settings;

/// <summary>테마 선택. 시스템이면 Windows 앱 모드를 따른다.</summary>
public enum ThemeChoice
{
    System,
    Light,
    Dark,
}

/// <summary>
/// 앱 설정(설정 페이지): 테마, 화면 크기, 언어, 창 크기와 위치 기억. 시작 프로그램 등록은 여기 없다 -
/// Windows 의 <c>Run</c> 키가 그 값의 주인이고 우리 키에 복사해 두면 둘이 어긋난다.
///
/// 저장 형식은 이름-문자열 쌍이다(오버레이 설정과 같다). PyQt5 는 <c>ThemeManager</c> 와 <c>UiScale</c> 두 키에
/// 나눠 썼고, 여기서는 한 키에 모은다.
/// </summary>
public sealed class AppSettings
{
    public const int MinScalePercent = 75;
    public const int MaxScalePercent = 125;
    public const int ScaleStepPercent = 5;
    public const int DefaultScalePercent = 100;

    /// <summary>표시 언어 코드. 새 언어는 <c>Strings.&lt;코드&gt;.xaml</c> 을 넣고 여기에 적는다.</summary>
    public static readonly IReadOnlyList<string> Languages = ["ko", "en"];

    public const string DefaultLanguage = "ko";

    public ThemeChoice Theme { get; set; } = ThemeChoice.System;

    private int _scalePercent = DefaultScalePercent;

    /// <summary>75-125 를 5 단위로 맞춘다(PyQt5 <c>normalize_scale</c> 과 같은 규칙).</summary>
    public int ScalePercent
    {
        get => _scalePercent;
        set => _scalePercent = NormalizeScale(value);
    }

    private string _language = DefaultLanguage;

    /// <summary>모르는 언어는 기본(한국어)이다.</summary>
    public string Language
    {
        get => _language;
        set => _language = Languages.Contains(value) ? value : DefaultLanguage;
    }

    /// <summary>끝낼 때 창 크기와 위치를 저장하고 다음 실행에 되살린다.</summary>
    public bool RememberWindow { get; set; } = true;

    /// <summary>마지막으로 기억한 창. 없으면 창은 기본 자리에서 열린다.</summary>
    public SavedWindowBounds? Window { get; set; }

    public double ScaleFactor => ScalePercent / 100.0;

    public static int NormalizeScale(double value)
    {
        if (double.IsNaN(value)) return DefaultScalePercent;
        var clamped = Math.Clamp(value, MinScalePercent, MaxScalePercent);
        var steps = Math.Round((clamped - MinScalePercent) / ScaleStepPercent, MidpointRounding.AwayFromZero);
        return MinScalePercent + (int)steps * ScaleStepPercent;
    }

    public static AppSettings FromValues(IReadOnlyDictionary<string, string> values)
    {
        string? Get(string key) => values.TryGetValue(key, out var v) ? v : null;

        var settings = new AppSettings
        {
            Theme = Get("theme") switch
            {
                "light" => ThemeChoice.Light,
                "dark" => ThemeChoice.Dark,
                _ => ThemeChoice.System,
            },
            Language = Get("language") ?? DefaultLanguage,
            // 저장한 적이 없으면 켠 채로 시작한다.
            RememberWindow = Get("remember_window") is not ("false" or "False" or "0"),
        };
        if (double.TryParse(Get("scale_percent"), NumberStyles.Float, CultureInfo.InvariantCulture, out var scale))
            settings.ScalePercent = NormalizeScale(scale);

        if (TryInt(Get("window_left"), out var left) && TryInt(Get("window_top"), out var top) &&
            TryInt(Get("window_width"), out var width) && TryInt(Get("window_height"), out var height) &&
            width > 0 && height > 0)
        {
            settings.Window = new SavedWindowBounds(left, top, width, height, Get("window_maximized") is "true" or "True" or "1");
        }
        return settings;
    }

    public IReadOnlyDictionary<string, string> ToValues()
    {
        var values = new Dictionary<string, string>
        {
            ["theme"] = Theme switch { ThemeChoice.Light => "light", ThemeChoice.Dark => "dark", _ => "system" },
            ["scale_percent"] = ScalePercent.ToString(CultureInfo.InvariantCulture),
            ["language"] = Language,
            ["remember_window"] = RememberWindow ? "true" : "false",
        };
        if (Window is { } w)
        {
            values["window_left"] = w.Left.ToString(CultureInfo.InvariantCulture);
            values["window_top"] = w.Top.ToString(CultureInfo.InvariantCulture);
            values["window_width"] = w.Width.ToString(CultureInfo.InvariantCulture);
            values["window_height"] = w.Height.ToString(CultureInfo.InvariantCulture);
            values["window_maximized"] = w.Maximized ? "true" : "false";
        }
        return values;
    }

    /// <summary>
    /// PyQt5 값에서 가져온다(처음 한 번). 테마와 화면 크기만 - 창 크기와 위치는 Qt 논리 픽셀이고 원본 창(920x640)이
    /// 이 앱의 최소 크기보다 작아 가져와도 쓸 수 없다(오버레이 좌표를 버린 D-023 과 같은 이유).
    /// <c>follow_system</c> 이 참이거나 테마가 system 이면 시스템 따르기다. PyQt5 의 "고대비" 구성표(theme=custom)는
    /// 이 앱에서 Windows 고대비를 켜야 나오므로 시스템 따르기로 옮긴다.
    /// </summary>
    public static AppSettings FromPyQt5(IReadOnlyDictionary<string, string>? themeManager, IReadOnlyDictionary<string, string>? uiScale)
    {
        var settings = new AppSettings();
        if (themeManager is not null)
        {
            var follow = themeManager.TryGetValue("follow_system", out var f) && f is "true" or "True" or "1";
            var theme = themeManager.GetValueOrDefault("theme", "system");
            settings.Theme = follow ? ThemeChoice.System : theme switch
            {
                "light" => ThemeChoice.Light,
                "dark" => ThemeChoice.Dark,
                _ => ThemeChoice.System,
            };
        }
        if (uiScale is not null &&
            double.TryParse(uiScale.GetValueOrDefault("scale_percent"), NumberStyles.Float, CultureInfo.InvariantCulture, out var scale))
            settings.ScalePercent = NormalizeScale(scale);
        return settings;
    }

    private static bool TryInt(string? text, out int value) =>
        int.TryParse(text, NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
}

/// <summary>
/// 기억한 메인 창. 단위는 WPF 논리 단위(DIP)다. <see cref="Maximized"/> 면 나머지는 "복원했을 때의" 자리다.
/// </summary>
public sealed record SavedWindowBounds(int Left, int Top, int Width, int Height, bool Maximized)
{
    /// <summary>
    /// 지금 화면 구성에서 보이는 자리로 고친다. 모니터를 뺐거나 해상도가 바뀌어 창이 화면 밖이면 사용자가 창을 찾을 수
    /// 없다. 크기는 최소~작업 영역으로 줄이고, 위치는 창이 작업 영역 안에 들어오게 밀어 넣는다.
    /// </summary>
    /// <param name="areaLeft">가상 화면(모든 모니터를 합친 사각형)의 왼쪽. 나머지 area 인자도 같은 사각형이다.</param>
    public SavedWindowBounds Fit(int areaLeft, int areaTop, int areaWidth, int areaHeight, int minWidth, int minHeight)
    {
        var width = Math.Clamp(Width, Math.Min(minWidth, areaWidth), areaWidth);
        var height = Math.Clamp(Height, Math.Min(minHeight, areaHeight), areaHeight);
        var left = Math.Clamp(Left, areaLeft, areaLeft + areaWidth - width);
        var top = Math.Clamp(Top, areaTop, areaTop + areaHeight - height);
        return new SavedWindowBounds(left, top, width, height, Maximized);
    }
}
