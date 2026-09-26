using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using WindowResizer.Core.Profiles;

namespace WindowResizer.Core.Tests;

/// <summary>
/// S2 게이트: 실사용 profiles.json 의 3단 왕복.
///   1. 원본을 임시 폴더에 복사한다. 원본은 어느 단계에서도 쓰지 않는다(해시로 확인).
///   2. C# 이 복사본을 오류 없이 읽고, 다시 쓴다.
///   3. PyQt5 앱의 <c>Profile.from_dict</c> 가 C# 이 쓴 파일을 원본과 같은 객체로 읽는다
///      (<c>next/tools/profile_roundtrip_check.py</c>).
///
/// 합성 샘플이 아니라 실파일로 잰다. 실파일이나 Python 이 없는 머신에서는 Inconclusive 다 -
/// 통과로 세지 않는다.
/// </summary>
[TestClass]
public sealed class ProfileRoundTripGateTests
{
    private const string RealProfilesPath = @"C:\app\profiles\profiles.json";

    [TestMethod]
    [TestCategory("Gate")]
    public void Real_profiles_survive_a_csharp_write_and_python_read_back()
    {
        if (!File.Exists(RealProfilesPath))
            Assert.Inconclusive("실사용 프로필 파일이 없다: " + RealProfilesPath);

        var python = Environment.GetEnvironmentVariable("WR_PYTHON") ?? @"C:\Python312\python.exe";
        if (!File.Exists(python))
            Assert.Inconclusive("Python 이 없다: " + python + " (WR_PYTHON 으로 지정)");

        var checker = FindChecker();
        var originalHash = Sha256(RealProfilesPath);

        var workDir = Path.Combine(Path.GetTempPath(), "wr-s2-gate-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(workDir);
        try
        {
            var copyPath = Path.Combine(workDir, "profiles.copy.json");
            var writtenPath = Path.Combine(workDir, "profiles.csharp.json");
            File.Copy(RealProfilesPath, copyPath);

            // 2단계: C# 읽기와 쓰기.
            var result = ProfileJson.Parse(File.ReadAllText(copyPath, Encoding.UTF8));
            Assert.IsEmpty(result.Errors,
                "C# 가 읽지 못한 프로필: " + string.Join("; ", result.Errors.Select(e => e.ProfileId + " " + e.Message)));
            Assert.IsNotEmpty(result.Document.Profiles);

            // BOM 없는 UTF-8. BOM 이 붙으면 Python json.load 가 실패한다.
            File.WriteAllText(writtenPath, ProfileJson.Serialize(result.Document), new UTF8Encoding(false));

            // 3단계: Python 이 다시 읽는다.
            var (exitCode, output) = Run(python, $"\"{checker}\" \"{copyPath}\" \"{writtenPath}\"");
            Assert.AreEqual(0, exitCode, "Python 왕복 검사 실패:\n" + output);
        }
        finally
        {
            Directory.Delete(workDir, recursive: true);
        }

        Assert.AreEqual(originalHash, Sha256(RealProfilesPath), "원본 profiles.json 이 바뀌었다");
    }

    private static string FindChecker()
    {
        for (var dir = new DirectoryInfo(AppContext.BaseDirectory); dir is not null; dir = dir.Parent)
        {
            var candidate = Path.Combine(dir.FullName, "tools", "profile_roundtrip_check.py");
            if (File.Exists(candidate)) return candidate;
        }
        Assert.Fail("next/tools/profile_roundtrip_check.py 를 찾지 못했다");
        return "";
    }

    private static (int ExitCode, string Output) Run(string fileName, string arguments)
    {
        var info = new ProcessStartInfo(fileName, arguments)
        {
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        info.Environment["PYTHONIOENCODING"] = "utf-8";

        using var process = Process.Start(info)!;
        var stdout = process.StandardOutput.ReadToEndAsync();
        var stderr = process.StandardError.ReadToEndAsync();
        if (!process.WaitForExit(120_000))
        {
            process.Kill(entireProcessTree: true);
            Assert.Fail("Python 왕복 검사가 2분 안에 끝나지 않았다");
        }
        return (process.ExitCode, stdout.Result + stderr.Result);
    }

    private static string Sha256(string path)
    {
        using var stream = File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(stream));
    }
}
