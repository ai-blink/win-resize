using System.Text.Json;
using System.Text.Json.Serialization;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Overlay;

/// <summary>
/// 오버레이 버튼 하나. 프로필과 무관하게 자기 이름과 <b>복원할 창 위치·크기</b>를 스스로 저장한다(D-032).
/// 누르면 직전에 쓰던 창을 이 자리로 옮긴다 - 어떤 창을 옮길지는 매칭이 아니라 직전 창이다.
/// 좌표는 프로필과 같은 Win32 물리 픽셀(가상 데스크톱)이다.
/// </summary>
public sealed class OverlayButton : IJsonOnDeserialized
{
    [JsonPropertyName("id")] public string Id { get; set; } = "";
    [JsonPropertyName("name")] public string Name { get; set; } = "";
    [JsonPropertyName("x")] public int X { get; set; }
    [JsonPropertyName("y")] public int Y { get; set; }
    [JsonPropertyName("width")] public int Width { get; set; }
    [JsonPropertyName("height")] public int Height { get; set; }
    [JsonPropertyName("is_maximized")] public bool IsMaximized { get; set; }

    /// <summary>생김새와 발동 방식. <see cref="OverlayStyle.Enabled"/> 는 버튼에서는 쓰지 않는다(있으면 뜬다).</summary>
    [JsonPropertyName("style")] public OverlayStyle Style { get; set; } = new() { Enabled = true };

    void IJsonOnDeserialized.OnDeserialized()
    {
        Style ??= new OverlayStyle { Enabled = true };
        Style.Normalize();
        Name ??= "";
    }

    /// <summary>복원할 자리가 창에 적용할 수 있는 값인가(폭과 높이가 양수).</summary>
    public bool HasPlace => Width > 0 && Height > 0;

    /// <summary>적용기에 넘기는 창 설정. 투명도, 항상 위, Z 순서는 건드리지 않는 값(프로필의 기본 상태)이다.</summary>
    public WindowConfiguration ToWindowConfiguration() => new()
    {
        X = X, Y = Y, Width = Width, Height = Height, IsMaximized = IsMaximized,
    };

    public OverlayButton Clone()
    {
        var copy = (OverlayButton)MemberwiseClone();
        copy.Style = JsonSerializer.Deserialize<OverlayStyle>(JsonSerializer.Serialize(Style)) ?? new OverlayStyle { Enabled = true };
        return copy;
    }

    /// <summary>프로필 하나의 오버레이(이름, 자리, 생김새)를 버튼으로 복사한다. 자리가 없는 프로필은 null.</summary>
    /// <remarks>
    /// 버튼 ID 를 프로필 ID 로 한다 - 옛 버튼 배치(<see cref="OverlaySettings.Layout"/>)가 프로필 ID 로 저장돼 있어서
    /// 그대로 이어진다. 새로 만드는 버튼은 GUID 라 겹치지 않는다.
    /// </remarks>
    public static OverlayButton? FromProfile(string profileId, Profile profile)
    {
        if (profile.WindowConfig is not { } config || config.Width <= 0 || config.Height <= 0) return null;

        var style = profile.OverlayStyle is null
            ? new OverlayStyle()
            : JsonSerializer.Deserialize<OverlayStyle>(JsonSerializer.Serialize(profile.OverlayStyle)) ?? new OverlayStyle();
        style.Enabled = true;
        return new OverlayButton
        {
            Id = profileId,
            Name = profile.Name,
            X = config.X, Y = config.Y, Width = config.Width, Height = config.Height,
            IsMaximized = config.IsMaximized,
            Style = style,
        };
    }

    public static string NewId() => Guid.NewGuid().ToString("N");
}
