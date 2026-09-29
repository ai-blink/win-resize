using WindowResizer.Core.Hotkeys;

namespace WindowResizer.Infrastructure.Windowing;

/// <summary>
/// <see cref="GlobalHotkeys"/> 위의 등록 조율기. 등록을 통째로 바꾸고(<see cref="Replace"/>), 눌린 등록 id 를
/// 계획의 <see cref="HotkeyBinding"/> 으로 되돌려 알린다. 무엇을 등록할지는 Core 계획(<c>HotkeyPlanner</c>)이 정한다.
/// </summary>
public sealed class HotkeyRegistrar : IHotkeyRegistrar, IDisposable
{
    private readonly GlobalHotkeys _hotkeys = new();
    private readonly object _gate = new();
    private readonly Dictionary<int, HotkeyBinding> _byId = new();

    public HotkeyRegistrar()
    {
        _hotkeys.Pressed += OnPressed;
    }

    public event Action<HotkeyBinding>? Activated;

    public IReadOnlyList<HotkeyRegistration> Replace(IReadOnlyList<HotkeyBinding> bindings)
    {
        lock (_gate)
        {
            foreach (var id in _byId.Keys) _hotkeys.Unregister(id);
            _byId.Clear();

            var results = new List<HotkeyRegistration>(bindings.Count);
            foreach (var binding in bindings)
            {
                var id = _hotkeys.Register(binding.Combination, out var error);
                if (id is { } registered) _byId[registered] = binding;
                results.Add(new HotkeyRegistration(binding, id is not null, error));
            }
            return results;
        }
    }

    public int Probe(HotkeyCombination combination)
    {
        lock (_gate)
        {
            if (_byId.Values.Any(b => b.Combination == combination)) return 0;
            var id = _hotkeys.Register(combination, out var error);
            if (id is { } probe) _hotkeys.Unregister(probe);
            return id is null ? error : 0;
        }
    }

    private void OnPressed(int id, HotkeyCombination _)
    {
        HotkeyBinding? binding;
        lock (_gate) binding = _byId.GetValueOrDefault(id);
        if (binding is not null) Activated?.Invoke(binding);
    }

    public void Dispose()
    {
        _hotkeys.Pressed -= OnPressed;
        _hotkeys.Dispose();
    }
}
