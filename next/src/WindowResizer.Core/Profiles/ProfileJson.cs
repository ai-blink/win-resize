using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace WindowResizer.Core.Profiles;

/// <summary>profiles.json 파일 전체. 키는 프로필 ID(16자리 16진)이고 순서를 보존한다.</summary>
public sealed class ProfileDocument
{
    public string Version { get; set; } = "1.0";

    /// <summary>Python 은 저장할 때마다 이 값을 현재 시각으로 덮는다. 읽고 쓰는 계약은 값을 건드리지 않는다.</summary>
    public double CreatedAt { get; set; }

    public List<KeyValuePair<string, Profile>> Profiles { get; } = new();

    /// <summary>
    /// 읽지 못한 프로필. 버리지 않고 원문 그대로 들고 있다가 저장할 때 다시 쓴다(D-022) - 파일을 손으로 고치면
    /// 되살아난다. 사용자가 목록에서 지울 때만 사라진다. 저장 위치는 읽은 프로필들 뒤다.
    /// </summary>
    public List<UnreadableProfile> Unreadable { get; } = new();

    public Profile? Find(string id) => Profiles.FirstOrDefault(p => p.Key == id).Value;

    /// <summary>
    /// 끝에 붙이고 ID 를 돌려준다. ID 규칙은 Python <c>Profile._generate_id</c> 와 같다:
    /// <c>sha256("이름_생성시각")</c> 앞 16자리. 겹치면(같은 초에 같은 이름) 뒤에 번호를 섞어 다시 만든다.
    /// </summary>
    public string Add(Profile profile, double now)
    {
        if (profile.CreatedAt == 0) profile.CreatedAt = now;
        profile.ModifiedAt = now;

        var seed = profile.Name + "_" + profile.CreatedAt.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
        var id = HashId(seed);
        for (var n = 2; Find(id) is not null || Unreadable.Any(u => u.Id == id); n++) id = HashId(seed + "_" + n);

        Profiles.Add(new(id, profile));
        return id;
    }

    /// <summary>같은 자리(순서 유지)에 바꿔 넣는다. 없는 ID 면 false.</summary>
    public bool Replace(string id, Profile profile, double now)
    {
        var index = Profiles.FindIndex(p => p.Key == id);
        if (index < 0) return false;
        profile.ModifiedAt = now;
        Profiles[index] = new(id, profile);
        return true;
    }

    /// <summary>읽은 프로필이든 읽지 못한 프로필이든 그 ID 를 지운다.</summary>
    public bool Remove(string id) =>
        Profiles.RemoveAll(p => p.Key == id) + Unreadable.RemoveAll(u => u.Id == id) > 0;

    /// <summary>
    /// 이름이 겹치지 않게 한다(D-021 결정 2): <c>Blender</c> 가 있으면 <c>Blender (2)</c>, <c>Blender (3)</c> ...
    /// 대소문자는 무시한다. <paramref name="exceptId"/> 는 편집 중인 자기 자신이다.
    /// </summary>
    public string UniqueName(string baseName, string? exceptId = null)
    {
        bool Taken(string name) => Profiles.Any(p => p.Key != exceptId &&
            string.Equals(p.Value.Name.Trim(), name, StringComparison.OrdinalIgnoreCase));

        var trimmed = baseName.Trim();
        if (!Taken(trimmed)) return trimmed;
        for (var n = 2; ; n++)
        {
            var candidate = $"{trimmed} ({n})";
            if (!Taken(candidate)) return candidate;
        }
    }

    private static string HashId(string seed) =>
        Convert.ToHexStringLower(System.Security.Cryptography.SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(seed)))[..16];
}

/// <summary>한 프로필을 읽다 실패한 기록. Python 과 같이 그 프로필만 건너뛰고 나머지는 읽는다.</summary>
public sealed record ProfileLoadError(string ProfileId, string Message);

/// <summary>
/// 읽지 못한 프로필 하나. <see cref="RawJson"/> 은 파일에 있던 값 그대로다.
/// <see cref="DisplayName"/> 은 원문에 문자열 <c>name</c> 이 있으면 그것, 없으면 ID 다 - 목록에서 알아보게.
/// </summary>
public sealed record UnreadableProfile(string Id, string RawJson, string Error)
{
    public string DisplayName
    {
        get
        {
            try
            {
                using var doc = JsonDocument.Parse(RawJson);
                if (doc.RootElement.ValueKind == JsonValueKind.Object &&
                    doc.RootElement.TryGetProperty("name", out var name) &&
                    name.ValueKind == JsonValueKind.String &&
                    !string.IsNullOrWhiteSpace(name.GetString()))
                    return name.GetString()!.Trim();
            }
            catch (JsonException)
            {
            }
            return Id;
        }
    }
}

public sealed record ProfileLoadResult(ProfileDocument Document, IReadOnlyList<ProfileLoadError> Errors);

/// <summary>
/// 기존 profiles.json 스키마를 바꾸지 않고 읽고 쓴다. 파일 입출력은 Infrastructure 몫이고
/// 여기서는 문자열만 다룬다.
///
/// 허용 범위는 Python <c>json</c> 모듈과 같게 엄격하다: 주석 불가, trailing comma 불가,
/// 키 대소문자 구분. PyQt5 가 못 읽는 파일을 C# 만 읽으면 되돌아갈 길이 끊긴다.
/// 쓰기는 Python 의 <c>json.dump(indent=2, ensure_ascii=False)</c> 와 같은 모양이다.
/// 파일로 쓸 때는 BOM 없는 UTF-8 이어야 한다 - BOM 이 붙으면 Python <c>json.load</c> 가 실패한다.
/// </summary>
public static class ProfileJson
{
    public static readonly JsonSerializerOptions Options = CreateOptions();

    private static JsonSerializerOptions CreateOptions()
    {
        var options = new JsonSerializerOptions
        {
            WriteIndented = true,
            IndentSize = 2,
            // 한글 이름이 \uXXXX 로 바뀌지 않게 한다(ensure_ascii=False 와 같은 결과).
            Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
            // null 도 키를 남긴다. Python 이 쓴 파일에 "overlay_style": null 이 있다.
            DefaultIgnoreCondition = JsonIgnoreCondition.Never,
            // Effective* 같은 계산 속성을 쓰지 않는다. 쓰면 Python from_dict 가 모르는 키로
            // TypeError 를 낸다(S2 게이트가 2026-09-27 에 실제로 잡았다).
            IgnoreReadOnlyProperties = true,
            PropertyNameCaseInsensitive = false,
            ReadCommentHandling = JsonCommentHandling.Disallow,
            AllowTrailingCommas = false,
        };
        options.Converters.Add(new JsonStringEnumConverter(JsonNamingPolicy.SnakeCaseLower, allowIntegerValues: false));
        return options;
    }

    public static ProfileLoadResult Parse(string json)
    {
        // BOM 이 붙은 파일이 들어와도 읽기는 한다. 쓸 때는 절대 붙이지 않는다.
        json = json.TrimStart('﻿');

        var document = new ProfileDocument();
        var errors = new List<ProfileLoadError>();

        using var parsed = JsonDocument.Parse(json, new JsonDocumentOptions
        {
            CommentHandling = JsonCommentHandling.Disallow,
            AllowTrailingCommas = false,
        });
        var root = parsed.RootElement;

        if (root.TryGetProperty("version", out var version) && version.ValueKind == JsonValueKind.String)
            document.Version = version.GetString()!;
        if (root.TryGetProperty("created_at", out var createdAt) && createdAt.ValueKind == JsonValueKind.Number)
            document.CreatedAt = createdAt.GetDouble();

        if (!root.TryGetProperty("profiles", out var profiles) || profiles.ValueKind != JsonValueKind.Object)
            return new ProfileLoadResult(document, errors);

        foreach (var entry in profiles.EnumerateObject())
        {
            try
            {
                var profile = entry.Value.Deserialize<Profile>(Options)
                    ?? throw new JsonException("프로필 값이 null 이다");
                if (string.IsNullOrWhiteSpace(profile.Name))
                    throw new JsonException("프로필 이름이 비어 있다");
                document.Profiles.Add(new(entry.Name, profile));
            }
            catch (Exception ex) when (ex is JsonException or InvalidOperationException or NotSupportedException)
            {
                errors.Add(new ProfileLoadError(entry.Name, ex.Message));
                document.Unreadable.Add(new UnreadableProfile(entry.Name, entry.Value.GetRawText(), ex.Message));
            }
        }

        return new ProfileLoadResult(document, errors);
    }

    /// <summary>
    /// 깊은 복사. 편집 창은 복사본을 고치고 저장할 때만 문서에 넣는다 - 취소하면 원본이 그대로다.
    /// 직렬화를 거치므로 모르는 키(<see cref="Profile.Extra"/>)도 같이 복사된다.
    /// </summary>
    public static Profile Clone(Profile profile) =>
        JsonSerializer.Deserialize<Profile>(JsonSerializer.Serialize(profile, Options), Options)!;

    public static string Serialize(ProfileDocument document)
    {
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer, new JsonWriterOptions
        {
            Indented = true,
            IndentSize = 2,
            Encoder = Options.Encoder,
        }))
        {
            writer.WriteStartObject();
            writer.WriteString("version", document.Version);
            writer.WriteNumber("created_at", document.CreatedAt);
            writer.WritePropertyName("profiles");
            writer.WriteStartObject();
            foreach (var (id, profile) in document.Profiles)
            {
                writer.WritePropertyName(id);
                JsonSerializer.Serialize(writer, profile, Options);
            }
            foreach (var unreadable in document.Unreadable)
            {
                writer.WritePropertyName(unreadable.Id);
                writer.WriteRawValue(unreadable.RawJson, skipInputValidation: false);
            }
            writer.WriteEndObject();
            writer.WriteEndObject();
        }

        return System.Text.Encoding.UTF8.GetString(buffer.ToArray());
    }
}
