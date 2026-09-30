using WindowResizer.Infrastructure.Hosting;

namespace WindowResizer.Infrastructure.Tests;

[TestClass]
public sealed class SingleInstanceGuardTests
{
    private static string UniqueName() => "WindowResizer.Tests." + Guid.NewGuid().ToString("N");

    [TestMethod]
    public void The_second_acquire_is_not_first_and_a_signal_reaches_the_first()
    {
        var name = UniqueName();
        using var first = SingleInstanceGuard.Acquire(name);
        using var got = new ManualResetEventSlim();
        first.Listen(got.Set);

        using var second = SingleInstanceGuard.Acquire(name);
        Assert.IsTrue(first.IsFirst);
        Assert.IsFalse(second.IsFirst);

        second.SignalFirst();
        Assert.IsTrue(got.Wait(3000), "첫 실행이 신호를 받아야 창을 앞으로 낼 수 있다");
    }

    [TestMethod]
    public void After_the_first_instance_ends_the_next_one_is_first_again()
    {
        var name = UniqueName();
        var first = SingleInstanceGuard.Acquire(name);
        first.Dispose();

        using var next = SingleInstanceGuard.Acquire(name);
        Assert.IsTrue(next.IsFirst);
    }

    [TestMethod]
    public void Different_names_do_not_block_each_other()
    {
        using var a = SingleInstanceGuard.Acquire(UniqueName());
        using var b = SingleInstanceGuard.Acquire(UniqueName());
        Assert.IsTrue(a.IsFirst && b.IsFirst);
    }
}
