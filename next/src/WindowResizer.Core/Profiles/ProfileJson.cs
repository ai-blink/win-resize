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
}

/// <summary>한 프로필을 읽다 실패한 기록. Python 과 같이 그 프로필만 건너뛰고 나머지는 읽는다.</summary>
public sealed record ProfileLoadError(string ProfileId, string Message);

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
            }
        }

        return new ProfileLoadResult(document, errors);
    }

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
            writer.WriteEndObject();
            writer.WriteEndObject();
        }

        return System.Text.Encoding.UTF8.GetString(buffer.ToArray());
    }
}
