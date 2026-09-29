using System.Collections.ObjectModel;
using System.Windows.Input;
using WindowResizer.App.Mvvm;
using WindowResizer.Core.Hotkeys;
using WindowResizer.Core.Profiles;

namespace WindowResizer.App.ViewModels;

/// <summary>
/// 단축키 쪽에서 밖으로 나가는 다섯 가지. 전부 없어도 앱은 뜬다(테스트) - 그때는 등록만 하지 않는다.
/// </summary>
/// <param name="Registrar">전역 단축키 등록기. 없으면 등록하지 않는다.</param>
/// <param name="ApplyAll">처음 값(저장소에서 읽은 것).</param>
/// <param name="Save">전체 적용 단축키 저장. 성공하면 null, 실패하면 원인.</param>
/// <param name="ToggleForegroundTopmost">전경 창의 항상 위를 뒤집는다. 창이 없으면 null.</param>
/// <param name="Post">UI 스레드로 넘긴다. 등록기는 자기 스레드에서 알리므로 상태를 건드리기 전에 반드시 거친다.</param>
public sealed record HotkeyServices(
    IHotkeyRegistrar? Registrar = null,
    ApplyAllHotkey? ApplyAll = null,
    Func<ApplyAllHotkey, string?>? Save = null,
    Func<(string Title, bool Topmost, bool Succeeded)?>? ToggleForegroundTopmost = null,
    Action<Action>? Post = null);

/// <summary>동작 콤보의 한 칸.</summary>
public sealed record HotkeyActionOption(HotkeyAction Action, string Display);

/// <summary>프로필 고르기 콤보의 한 칸.</summary>
public sealed record HotkeyProfileChoice(string Id, string Name);

/// <summary>등록 상태 목록의 한 줄.</summary>
public sealed record HotkeyStatusRow(string Label, string Text, string Action, string State, bool IsProblem);

/// <summary>프로필 단축키 세트 하나의 편집 값.</summary>
public sealed class HotkeySetRow : ObservableObject
{
    private bool _enabled;
    private string _combination = "";
    private HotkeyAction _action = HotkeyAction.ApplyProfile;

    public bool Enabled { get => _enabled; set => Set(ref _enabled, value); }
    public string Combination { get => _combination; set => Set(ref _combination, value); }
    public HotkeyAction Action { get => _action; set => Set(ref _action, value); }
}

/// <summary>
/// 단축키 페이지(메뉴 지도 [단축키]). 세 가지를 맡는다:
/// 전체 적용 단축키 편집, 프로필별 세트(최대 3개)와 동작 편집, 등록 결과 목록.
///
/// 무엇을 등록할지는 문서가 정한다(Core <see cref="HotkeyPlanner"/>) - 프로필을 저장하거나 지울 때마다
/// <see cref="MainViewModel"/> 이 <see cref="Sync"/> 를 불러 통째로 다시 등록한다(PyQt5 와 같다).
/// 프로필 변경은 전부 <see cref="MainViewModel.SaveProfileHotkeys"/> 를 거친다(D-022).
/// </summary>
public sealed class HotkeysViewModel : ObservableObject
{
    /// <summary>편집 창이 한 프로필에 쓰는 세트 수(PyQt5 와 같다).</summary>
    public const int SetsPerProfile = 3;

    private readonly MainViewModel _owner;
    private readonly HotkeyServices _services;
    private readonly Func<string, string> _text;
    private readonly Action<Action> _post;

    private ApplyAllHotkey _applyAll;
    private bool _applyAllEnabled;
    private string _applyAllCombination;
    private string _applyAllError = "";
    private string _applyAllState = "";

    private HotkeyProfileChoice? _selectedProfile;
    private bool _rebuildingChoices;
    private bool _profileHotkeysEnabled;
    private string _profileError = "";

    public HotkeysViewModel(MainViewModel owner, HotkeyServices services, Func<string, string> text)
    {
        _owner = owner;
        _services = services;
        _text = text;
        _post = services.Post ?? (action => action());

        _applyAll = services.ApplyAll ?? ApplyAllHotkey.Off;
        _applyAllEnabled = _applyAll.Enabled;
        _applyAllCombination = _applyAll.Combination;

        ActionOptions = HotkeyActions.ProfileActions
            .Select(a => new HotkeyActionOption(a, text("Hotkey.Action." + HotkeyActions.ToKey(a))))
            .ToList();
        for (var i = 0; i < SetsPerProfile; i++) Sets.Add(new HotkeySetRow());

        SaveApplyAllCommand = new RelayCommand(SaveApplyAll);
        SaveProfileCommand = new RelayCommand(SaveProfile, () => SelectedProfile is not null);

        if (services.Registrar is { } registrar)
            registrar.Activated += binding => _post(() => _owner.RunHotkey(binding));
    }

    public IReadOnlyList<HotkeyActionOption> ActionOptions { get; }
    public ObservableCollection<HotkeySetRow> Sets { get; } = new();
    public ObservableCollection<HotkeyProfileChoice> ProfileChoices { get; } = new();
    public ObservableCollection<HotkeyStatusRow> Rows { get; } = new();

    public ICommand SaveApplyAllCommand { get; }
    public ICommand SaveProfileCommand { get; }

    // --- 전체 적용 단축키 -------------------------------------------------------------

    public bool ApplyAllEnabled { get => _applyAllEnabled; set => Set(ref _applyAllEnabled, value); }
    public string ApplyAllCombination { get => _applyAllCombination; set => Set(ref _applyAllCombination, value); }

    /// <summary>입력이 틀렸을 때의 이유. 비어 있으면 문제없다.</summary>
    public string ApplyAllError { get => _applyAllError; private set => Set(ref _applyAllError, value); }

    /// <summary>저장한 전체 적용 단축키의 등록 결과 한 줄.</summary>
    public string ApplyAllState { get => _applyAllState; private set => Set(ref _applyAllState, value); }

    /// <summary>
    /// 검사하고 저장하고 다시 등록한다. PyQt5 와 같이 <b>등록에 실패해도 저장은 한다</b> -
    /// 다른 프로그램이 쓰고 있는 조합은 그 프로그램을 닫으면 다시 쓸 수 있다.
    /// </summary>
    public void SaveApplyAll()
    {
        var text = ApplyAllCombination.Trim();
        if (ApplyAllEnabled && !HotkeyCombination.TryParse(text, out _))
        {
            ApplyAllError = _text("Hotkeys.Error.Invalid");
            return;
        }
        ApplyAllError = "";

        var next = new ApplyAllHotkey(ApplyAllEnabled, text);
        var error = (_services.Save ?? (_ => null))(next);
        if (error is not null)
        {
            _owner.ShowStatus(string.Format(_text("Status.SettingsSaveFailed"), error));
            return;
        }

        _applyAll = next;
        ApplyAllCombination = text;
        Sync();
        _owner.ShowStatus(!next.Enabled
            ? _text("Status.HotkeyApplyAllOff")
            : Registered(ApplyAllRegistrationKey)
                ? string.Format(_text("Status.HotkeyApplyAllOn"), next.Combination)
                : _text("Status.HotkeyApplyAllNotRegistered"));
    }

    // --- 프로필 세트 ------------------------------------------------------------------

    /// <summary>편집할 프로필. 목록이 다시 만들어져도 같은 프로필이 계속 선택되어 있다.</summary>
    public HotkeyProfileChoice? SelectedProfile
    {
        get => _selectedProfile;
        set
        {
            // 목록을 비우는 순간 화면이 null 을 써 넣는다. 그건 사용자의 선택이 아니다.
            if (value is null && _rebuildingChoices) return;
            if (!Set(ref _selectedProfile, value)) return;
            LoadEditor();
        }
    }

    public bool HasSelectedProfile => SelectedProfile is not null;

    /// <summary>프로필의 단축키 전체 스위치(<c>hotkey_enabled</c>).</summary>
    public bool ProfileHotkeysEnabled { get => _profileHotkeysEnabled; set => Set(ref _profileHotkeysEnabled, value); }

    public string ProfileError { get => _profileError; private set => Set(ref _profileError, value); }

    /// <summary>
    /// 검사하고 저장한다. 저장은 활성화된 세트 중 조합이 있는 것만 남긴다(PyQt5 <c>_collect_hotkey_sets</c>).
    /// 첫 세트는 단일 필드(<c>hotkey_combination</c>, <c>hotkey_action</c>)에도 적는다 - 옛 프로그램이 읽는 자리다.
    /// </summary>
    public void SaveProfile()
    {
        if (SelectedProfile is not { } choice) return;

        var sets = new List<HotkeySet>();
        foreach (var row in Sets.Where(s => s.Enabled && s.Combination.Trim().Length > 0))
        {
            var text = row.Combination.Trim();
            if (!HotkeyCombination.TryParse(text, out _))
            {
                ProfileError = string.Format(_text("Hotkeys.Error.SetInvalid"), text);
                return;
            }
            sets.Add(new HotkeySet { Enabled = true, Combination = text, Action = HotkeyActions.ToKey(row.Action) });
        }
        ProfileError = "";

        _owner.SaveProfileHotkeys(choice.Id, ProfileHotkeysEnabled, sets);
    }

    private void LoadEditor()
    {
        OnPropertyChanged(nameof(HasSelectedProfile));
        ProfileError = "";

        var profile = _selectedProfile is null ? null : _owner.FindProfile(_selectedProfile.Id);
        ProfileHotkeysEnabled = profile?.HotkeyEnabled ?? false;

        var effective = profile is null ? [] : HotkeyPlanner.EffectiveSets(profile);
        for (var i = 0; i < Sets.Count; i++)
        {
            var source = i < effective.Count ? effective[i] : null;
            Sets[i].Enabled = source?.Enabled ?? false;
            Sets[i].Combination = source?.Combination ?? "";
            Sets[i].Action = source is not null && HotkeyActions.TryParseProfileAction(source.Action, out var action)
                ? action
                : HotkeyAction.ApplyProfile;
        }
    }

    // --- 등록 -------------------------------------------------------------------------

    private const string ApplyAllRegistrationKey = "apply-all";

    private readonly Dictionary<string, bool> _registered = new();
    private IReadOnlyList<HotkeyBinding> _lastBindings = [];
    private IReadOnlyList<HotkeyFailure> _lastFailures = [];
    private bool _lastAllRegistered;

    private bool Registered(string key) => _registered.GetValueOrDefault(key);

    /// <summary>
    /// 문서와 전체 적용 단축키에서 등록 대상을 다시 뽑아 통째로 등록하고 목록을 갱신한다.
    /// 프로필 목록이 바뀌었으니 편집 콤보도 함께 다시 만든다.
    /// </summary>
    public void Sync()
    {
        RebuildChoices();

        var plan = _owner.PlanHotkeys();
        var bindings = new List<HotkeyBinding>();
        if (_applyAll.Enabled && HotkeyCombination.TryParse(_applyAll.Combination, out var all))
        {
            bindings.Add(new HotkeyBinding(HotkeyAction.ApplyAllProfiles, all, _applyAll.Combination, null,
                _text("Hotkeys.ApplyAll.Label")));
        }
        bindings.AddRange(plan.Bindings);

        // 적용 횟수 저장처럼 단축키와 무관한 변경마다 등록을 지웠다 다시 하지 않는다 - 눌러서 실행하는 도중에
        // 자기 등록이 사라졌다 돌아온다. 같은 계획이고 전부 성공했으면 그대로 둔다(실패가 있으면 다시 시도한다).
        if (_lastAllRegistered && bindings.SequenceEqual(_lastBindings) && plan.Failures.SequenceEqual(_lastFailures))
            return;
        _lastBindings = bindings;
        _lastFailures = plan.Failures;

        Rows.Clear();
        _registered.Clear();
        ApplyAllState = "";

        var registrar = _services.Registrar;
        _lastAllRegistered = false;
        if (registrar is not null)
        {
            var results = registrar.Replace(bindings);
            _lastAllRegistered = results.All(r => r.Registered);
            foreach (var result in results)
            {
                var binding = result.Binding;
                var state = result.Registered ? _text("Hotkeys.State.Registered") : DescribeFailure(result.ErrorCode);
                if (binding.Action == HotkeyAction.ApplyAllProfiles)
                {
                    _registered[ApplyAllRegistrationKey] = result.Registered;
                    ApplyAllState = state;
                }
                else
                {
                    Rows.Add(new HotkeyStatusRow(binding.Label, binding.Text, ActionText(binding.Action), state, !result.Registered));
                }
            }
        }

        // 계획 단계에서 걸러진 것도 보인다 - 조용히 빠지면 왜 안 눌리는지 알 길이 없다.
        foreach (var failure in plan.Failures)
            Rows.Add(new HotkeyStatusRow(failure.Label, failure.Text, "", DescribeFailure(failure), IsProblem: true));

        if (_applyAll.Enabled && !HotkeyCombination.TryParse(_applyAll.Combination, out _))
            ApplyAllState = _text("Hotkeys.State.Invalid");
    }

    private void RebuildChoices()
    {
        var keep = SelectedProfile?.Id;
        _rebuildingChoices = true;
        try
        {
            ProfileChoices.Clear();
            foreach (var row in _owner.Profiles.Where(p => !p.IsUnreadable))
                ProfileChoices.Add(new HotkeyProfileChoice(row.Id, row.Name));
        }
        finally
        {
            _rebuildingChoices = false;
        }

        // 지운 프로필이면 비운다. 같은 프로필이면 record 값 비교가 같아 선택 알림이 없으므로 편집 값은 항상 다시 읽는다.
        SelectedProfile = keep is null ? null : ProfileChoices.FirstOrDefault(c => c.Id == keep);
        LoadEditor();
    }

    private string ActionText(HotkeyAction action) => _text("Hotkey.Action." + HotkeyActions.ToKey(action));

    private string DescribeFailure(int errorCode) => errorCode == 1409
        ? _text("Hotkeys.State.InUse")
        : string.Format(_text("Hotkeys.State.Failed"), errorCode);

    private string DescribeFailure(HotkeyFailure failure) => failure.Reason switch
    {
        HotkeyFailureReason.InvalidCombination => _text("Hotkeys.State.Invalid"),
        HotkeyFailureReason.UnknownAction => _text("Hotkeys.State.UnknownAction"),
        HotkeyFailureReason.Duplicate => _text("Hotkeys.State.Duplicate"),
        _ => DescribeFailure(failure.ErrorCode),
    };
}
