using System.Runtime.InteropServices;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Infrastructure.Windowing;

namespace WindowResizer.Infrastructure.Tests;

/// <summary>
/// 등록 조율기의 라이브 게이트(D-026): 실제 키 입력이 계획의 바인딩으로 돌아오는가, 통째로 바꾸면 옛 등록이
/// 사라지는가, 충돌이 오류 코드로 보이는가. 시스템 전역 자원이라 병렬로 돌리지 않는다.
/// </summary>
[TestClass]
[DoNotParallelize]
public sealed class HotkeyRegistrarLiveTests
{
    /// <summary>다른 프로그램이 쓸 일이 거의 없는 조합(InputAndEventLiveTests 는 F24 를 쓴다).</summary>
    private const string ProbeText = "Ctrl+Alt+Shift+F23";

    private static HotkeyBinding Binding(string profileId, HotkeyAction action = HotkeyAction.ApplyProfile) =>
        new(action, HotkeyCombination.Parse(ProbeText), ProbeText, profileId, "probe " + profileId);

    [TestMethod]
    [TestCategory("Live")]
    public void A_real_key_press_comes_back_as_the_registered_binding_and_replace_drops_the_old_one()
    {
        using var registrar = new HotkeyRegistrar();
        var pressed = new List<HotkeyBinding>();
        var fired = new ManualResetEventSlim();
        registrar.Activated += b => { lock (pressed) pressed.Add(b); fired.Set(); };

        var first = registrar.Replace([Binding("first")]).Single();
        if (!first.Registered && first.ErrorCode == 1409)
            Assert.Inconclusive("다른 프로그램이 이미 " + ProbeText + " 를 잡고 있다");
        Assert.IsTrue(first.Registered, "등록 실패, Win32 오류 " + first.ErrorCode);

        PressProbe();
        Assert.IsTrue(fired.Wait(TimeSpan.FromSeconds(2)), "단축키를 눌렀는데 Activated 가 오지 않았다");
        lock (pressed) Assert.AreEqual("first", pressed.Single().ProfileId, "눌린 것은 등록한 바인딩이어야 한다(동작과 프로필 포함)");

        // 통째로 바꾸면 옛 등록이 사라지고 새 바인딩이 대신 온다. 같은 조합을 다시 등록해도 충돌하지 않는다.
        fired.Reset();
        var second = registrar.Replace([Binding("second", HotkeyAction.AutoApplyToggle)]).Single();
        Assert.IsTrue(second.Registered, "옛 등록을 지우지 않아 새 등록이 충돌했다: " + second.ErrorCode);
        PressProbe();
        Assert.IsTrue(fired.Wait(TimeSpan.FromSeconds(2)));
        lock (pressed)
        {
            Assert.AreEqual("second", pressed.Last().ProfileId);
            Assert.AreEqual(HotkeyAction.AutoApplyToggle, pressed.Last().Action);
        }

        // 비우면 더 이상 오지 않는다.
        registrar.Replace([]);
        fired.Reset();
        PressProbe();
        Assert.IsFalse(fired.Wait(TimeSpan.FromMilliseconds(600)), "등록을 지웠는데 단축키가 아직 온다");
    }

    [TestMethod]
    [TestCategory("Live")]
    public void A_combination_held_by_another_registrar_is_reported_with_the_conflict_code_and_the_rest_still_register()
    {
        using var holder = new HotkeyRegistrar();
        var held = holder.Replace([Binding("holder")]).Single();
        if (!held.Registered) Assert.Inconclusive("조합을 잡지 못했다: " + held.ErrorCode);

        using var other = new HotkeyRegistrar();
        var free = new HotkeyBinding(HotkeyAction.ApplyProfile, HotkeyCombination.Parse("Ctrl+Alt+Shift+F22"),
            "Ctrl+Alt+Shift+F22", "free", "free");
        var results = other.Replace([Binding("conflict"), free]);

        Assert.IsFalse(results[0].Registered);
        Assert.AreEqual(1409, results[0].ErrorCode, "ERROR_HOTKEY_ALREADY_REGISTERED 여야 한다");
        if (!results[1].Registered && results[1].ErrorCode == 1409)
            Assert.Inconclusive("다른 프로그램이 Ctrl+Alt+Shift+F22 를 잡고 있다");
        Assert.IsTrue(results[1].Registered, "하나가 실패해도 나머지는 등록해야 한다");
    }

    private static void PressProbe()
    {
        var keys = new ushort[] { 0x11, 0x12, 0x10, 0x86 }; // Ctrl Alt Shift F23
        try
        {
            SendKeys(keys, up: false);
        }
        finally
        {
            SendKeys(keys.Reverse().ToArray(), up: true);
        }
    }

    // --- 테스트 전용 입력 주입 ------------------------------------------------------

    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public nint dwExtraInfo; }

    [StructLayout(LayoutKind.Explicit, Size = 40)]
    private struct INPUT
    {
        [FieldOffset(0)] public uint type;
        [FieldOffset(8)] public KEYBDINPUT ki;
    }

    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint count, INPUT[] inputs, int size);

    private static void SendKeys(ushort[] keys, bool up)
    {
        const uint KEYEVENTF_KEYUP = 0x0002;
        var inputs = keys.Select(k => new INPUT
        {
            type = 1,
            ki = new KEYBDINPUT { wVk = k, dwFlags = up ? KEYEVENTF_KEYUP : 0 },
        }).ToArray();
        var sent = SendInput((uint)inputs.Length, inputs, Marshal.SizeOf<INPUT>());
        Assert.AreEqual((uint)inputs.Length, sent, "SendInput 이 입력을 다 보내지 못했다(UIPI 차단일 수 있다)");
    }
}
