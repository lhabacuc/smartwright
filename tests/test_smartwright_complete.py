import asyncio
from pathlib import Path

from smartwright import Smartwright
from smartwright.ai_recovery.recovery import AIRecovery
from smartwright.api_executor.executor import ApiExecutor
from smartwright.core.engine import DecisionEngine
from smartwright.core.models import ApiKnowledge, StrategyResult
from smartwright.core.store import KnowledgeStore
from smartwright.fingerprint.tracker import FingerprintTracker
from smartwright.healing.layer import HealingLayer
from smartwright.intent.manager import IntentManager
from smartwright.network_learning.observer import NetworkLearner
from smartwright.resolver.adaptive import AdaptiveResolver
from smartwright.semantic_finder.finder import SemanticFinder


def run(coro):
    return asyncio.run(coro)


class FakeElement:
    def __init__(self, role=None, name="", label="", text="", tag="div", attrs=None):
        self.role = role
        self.name = name
        self.label = label
        self.text = text
        self.tag = tag
        self.attrs = attrs or {}
        self.clicked = False
        self.filled_value = None
        self.fail_click_once = False

    async def click(self):
        if self.fail_click_once:
            self.fail_click_once = False
            raise RuntimeError("transient click failure")
        self.clicked = True
        return "clicked"

    async def fill(self, value):
        self.filled_value = value
        return "filled"

    async def inner_text(self):
        return self.text

    async def get_attribute(self, name):
        return self.attrs.get(name)


class FakeLocatorGroup:
    def __init__(self, items):
        self.items = list(items)

    async def count(self):
        return len(self.items)

    def nth(self, idx):
        return self.items[idx]

    @property
    def first(self):
        return self.items[0]


class FakePage:
    def __init__(self, elements=None, url="https://example.test/login"):
        self.elements = list(elements or [])
        self.url = url
        self.state_waited = []
        self.handlers = {}
        self.goto_calls = []
        self.html_override = None

    def on(self, event, callback):
        self.handlers[event] = callback

    async def goto(self, url):
        self.url = url
        self.goto_calls.append(url)

    async def wait_for_load_state(self, state):
        self.state_waited.append(state)

    async def content(self):
        if self.html_override is not None:
            return self.html_override
        chunks = []
        for e in self.elements:
            attrs = " ".join(f'{k}="{v}"' for k, v in e.attrs.items())
            role = f' role="{e.role}"' if e.role else ""
            chunks.append(f"<{e.tag}{role} {attrs}>{e.text}</{e.tag}>")
        return "".join(chunks)

    def get_by_role(self, role, name=None):
        def match(el):
            if el.role != role:
                return False
            if name is None:
                return True
            hay = " ".join([el.name, el.label, el.text, el.attrs.get("aria-label", "")]).lower()
            return name.lower() in hay

        return FakeLocatorGroup([e for e in self.elements if match(e)])

    def get_by_label(self, label):
        label_low = label.lower()

        def match(el):
            hay = " ".join([el.label, el.attrs.get("placeholder", ""), el.attrs.get("name", "")]).lower()
            return label_low in hay

        return FakeLocatorGroup([e for e in self.elements if match(e)])

    def get_by_text(self, text):
        text_low = text.lower()

        def match(el):
            hay = " ".join([el.text, el.name, el.label]).lower()
            return text_low in hay

        return FakeLocatorGroup([e for e in self.elements if match(e)])

    def locator(self, tag):
        return FakeLocatorGroup([e for e in self.elements if e.tag == tag])


class FakeStreamingPage:
    def __init__(self, values):
        self.values = list(values)
        self.i = 0

    async def evaluate(self, _script):
        if self.i < len(self.values):
            out = self.values[self.i]
            self.i += 1
            return out
        return self.values[-1] if self.values else ""

    def locator(self, _selector):
        return FakeLocatorGroup([])


class FakeCopyButtonPage:
    def __init__(self, appear_after_polls=2):
        self.appear_after_polls = appear_after_polls
        self.polls = 0
        self.clicked = False

    async def evaluate(self, _script):
        self.polls += 1
        if self.polls > self.appear_after_polls:
            self.clicked = True
            return True
        return False

    def get_by_role(self, _role, name=None):
        _ = name
        return FakeLocatorGroup([])

    def locator(self, _selector):
        return FakeLocatorGroup([])


class FakeRequestContext:
    def __init__(self):
        self.calls = []

    async def get(self, endpoint, headers=None):
        self.calls.append(("GET", endpoint, headers, None))
        return {"method": "GET", "endpoint": endpoint}

    async def post(self, endpoint, headers=None, data=None):
        self.calls.append(("POST", endpoint, headers, data))
        return {"method": "POST", "endpoint": endpoint, "data": data}

    async def put(self, endpoint, headers=None, data=None):
        self.calls.append(("PUT", endpoint, headers, data))
        return {"method": "PUT", "endpoint": endpoint, "data": data}

    async def delete(self, endpoint, headers=None, data=None):
        self.calls.append(("DELETE", endpoint, headers, data))
        return {"method": "DELETE", "endpoint": endpoint, "data": data}


class FakeRequest:
    def __init__(self, url, method="POST", headers=None, payload=None):
        self.url = url
        self.method = method
        self.headers = headers or {}
        self._payload = payload or {}

    def post_data_json(self):
        return self._payload


class FakeResponse:
    def __init__(self, url, request, status=200, headers=None):
        self.url = url
        self.request = request
        self.status = status
        self.headers = headers or {"content-type": "application/json"}

    async def json(self):
        return {}

    async def text(self):
        return "{}"


def test_knowledge_store_persistence_and_scores(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.json")
    store.append_result(StrategyResult(intent="login_button", strategy="get_by_role", success=True, elapsed_ms=10))
    store.append_result(StrategyResult(intent="login_button", strategy="get_by_role", success=False, elapsed_ms=15))
    store.append_result(StrategyResult(intent="login_button", strategy="get_by_text", success=True, elapsed_ms=20))

    scores = store.strategy_scores("login_button")
    assert scores["get_by_role"] == 0.5
    assert scores["get_by_text"] == 1.0

    api = ApiKnowledge(intent="login_button", endpoint="https://x/api/login", method="POST")
    store.save_api(api)
    loaded = store.get_api("login_button")
    assert loaded is not None
    assert loaded.endpoint.endswith("/api/login")


def test_intent_manager_hints_and_suggest(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.json")
    intents = {"login_button": ["Entrar", "Login", "Sign in"]}
    manager = IntentManager(intents, store)

    hints = manager.all_hints("login_button")
    assert "login button" in hints
    assert "Login" in hints
    assert manager.suggest("clicar no login agora") == "login_button"


def test_fingerprint_change_detection(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.json")
    tracker = FingerprintTracker(store)
    page = FakePage([FakeElement(text="A")])

    first = run(tracker.detect_change(page, "page-1"))
    page.elements = [FakeElement(text="B")]
    second = run(tracker.detect_change(page, "page-1"))

    assert first is False
    assert second is True


def test_semantic_finder_returns_candidate_from_role_patterns():
    finder = SemanticFinder(
        semantic_map={
            "chat_list_msg": {
                "roles": ["article"],
                "patterns": ["conversation"],
            }
        }
    )
    page = FakePage([FakeElement(role="article", text="Latest conversation with support")])

    result = run(finder.find(page, "chat_list_msg", ["chat"]))
    assert result is not None
    assert run(result.inner_text()) == "Latest conversation with support"


def test_adaptive_resolver_falls_back_to_label(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.json")
    resolver = AdaptiveResolver(store, SemanticFinder())

    email = FakeElement(role=None, label="Email", tag="input")
    page = FakePage([email])

    locator = run(resolver.resolve(page, "email_field", ["Email"]))
    assert locator is email

    scores = store.strategy_scores("email_field")
    assert "get_by_role" in scores
    assert "get_by_label" in scores


def test_api_executor_dispatches_methods():
    executor = ApiExecutor()
    rc = FakeRequestContext()

    run(executor.execute(rc, ApiKnowledge(intent="i1", endpoint="/a", method="GET")))
    run(executor.execute(rc, ApiKnowledge(intent="i2", endpoint="/b", method="POST"), payload={"x": 1}))
    run(executor.execute(rc, ApiKnowledge(intent="i3", endpoint="/c", method="PUT"), payload={"x": 2}))
    run(executor.execute(rc, ApiKnowledge(intent="i4", endpoint="/d", method="DELETE"), payload={"x": 3}))

    methods = [m for m, *_ in rc.calls]
    assert methods == ["GET", "POST", "PUT", "DELETE"]


def test_healing_layer_retries_adaptively():
    healing = HealingLayer()
    calls = {"n": 0, "reload": 0, "relearn": 0}

    async def action():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("first fails")
        return "ok"

    async def reload_state():
        calls["reload"] += 1

    async def relearn():
        calls["relearn"] += 1

    out = run(healing.run_with_healing(action, reload_state, relearn))
    assert out == "ok"
    assert calls == {"n": 2, "reload": 1, "relearn": 1}


def test_network_learning_discovers_api_knowledge(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "knowledge.json")
    learner = NetworkLearner(store)

    req = FakeRequest(
        url="https://svc.test/api/messages/list",
        method="POST",
        headers={"Authorization": "Bearer token", "X-Trace": "1"},
        payload={"page": 1},
    )
    learner._on_request(req)

    resp = FakeResponse(url=req.url, request=req)
    run(learner._on_response(resp))

    # Intent agora e inferido como api:messages (keyword "message" no path)
    k = store.get_api("api:messages:create")
    assert k is not None
    assert k.method == "POST"
    assert k.payload_template == {"page": 1}
    assert "Authorization" in k.headers
    assert "X-Trace" not in k.headers

    # Verificar que discoveries foram registadas
    assert len(learner.discoveries) == 1
    assert learner.discoveries[0]["method"] == "POST"

    # Verificar summary
    s = learner.summary()
    assert s["total_discovered"] == 1
    assert "api:messages:create" in s["intents"]


def test_ai_recovery_extracts_snippet_and_suggests():
    recovery = AIRecovery()
    page = FakePage()
    page.html_override = "<div>noise</div><button>Sign in now</button><p>other</p>"

    suggestion = run(recovery.recover(page, "login_button", ["Sign in", "Login"]))
    assert suggestion is not None
    assert suggestion["strategy"] == "get_by_text"


def test_decision_engine_prefers_api_when_known(tmp_path: Path):
    page = FakePage([FakeElement(role="button", text="Login")])
    rc = FakeRequestContext()
    intents = {"login_button": ["Login"]}
    engine = DecisionEngine(page=page, request_context=rc, intents=intents, store_path=str(tmp_path / "k.json"))

    engine.store.save_api(ApiKnowledge(intent="login_button", endpoint="https://svc.test/api/login", method="POST"))
    result = run(engine.run(action="click", intent="login_button", value={"u": "a"}))

    assert result["method"] == "POST"
    assert rc.calls[0][1] == "https://svc.test/api/login"
    assert page.elements[0].clicked is False


def test_decision_engine_dom_path_with_healing(tmp_path: Path):
    btn = FakeElement(role="button", name="Login", text="Login")
    btn.fail_click_once = True
    page = FakePage([btn])
    rc = FakeRequestContext()
    intents = {"login_button": ["Login"]}
    engine = DecisionEngine(page=page, request_context=rc, intents=intents, store_path=str(tmp_path / "k.json"))

    result = run(engine.run(action="click", intent="login_button"))
    assert result == "clicked"
    assert btn.clicked is True
    assert page.state_waited == ["domcontentloaded"]


def test_decision_engine_uses_ai_recovery_when_dom_fails(tmp_path: Path):
    page = FakePage([FakeElement(role="button", text="Sign in")])
    rc = FakeRequestContext()
    intents = {"login_button": ["Sign in"]}
    engine = DecisionEngine(page=page, request_context=rc, intents=intents, store_path=str(tmp_path / "k.json"))

    async def always_fail(*_args, **_kwargs):
        raise LookupError("resolver failed")

    class _Advisor:
        async def suggest(self, intent, hints, snippets):
            return {"strategy": "get_by_text", "hint": "Sign in"}

    engine.ai_recovery = AIRecovery(advisor=_Advisor())
    engine.resolver.resolve = always_fail
    result = run(engine.run(action="click", intent="login_button"))
    assert result == "clicked"
    assert page.elements[0].clicked is True


def test_smartwright_public_api_end_to_end(tmp_path: Path):
    email = FakeElement(role="textbox", label="Email", tag="input")
    password = FakeElement(role="textbox", label="Password", tag="input")
    login = FakeElement(role="button", name="Login", text="Login")
    page = FakePage([email, password, login])
    rc = FakeRequestContext()

    smart = Smartwright(
        page=page,
        request_context=rc,
        intents={
            "email_field": ["Email"],
            "password_field": ["Password"],
            "login_button": ["Login"],
        },
        store_path=str(tmp_path / "k.json"),
    )

    run(smart.goto("https://example.test/login"))
    run(smart.fill("email_field", "user@example.com"))
    run(smart.fill("password_field", "s3cr3t"))
    run(smart.click("login_button"))

    assert page.goto_calls == ["https://example.test/login"]
    assert email.filled_value == "user@example.com"
    assert password.filled_value == "s3cr3t"
    assert login.clicked is True
    assert "request" in page.handlers
    assert "response" in page.handlers


def test_smartwright_emergency_type_index_api(tmp_path: Path):
    email = FakeElement(role="textbox", label="Email", tag="input")
    password = FakeElement(role="textbox", label="Password", tag="input")
    page = FakePage([email, password])
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    run(smart.emergency_fill("input", 0, "first@example.com"))
    run(smart.emergency_fill("input", 1, "s3cr3t"))

    assert email.filled_value == "first@example.com"
    assert password.filled_value == "s3cr3t"


def test_smartwright_emergency_role_and_text_api(tmp_path: Path):
    b1 = FakeElement(role="button", text="Cancel", name="Cancel", tag="button")
    b2 = FakeElement(role="button", text="Send", name="Send", tag="button")
    page = FakePage([b1, b2])
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    run(smart.emergency_click_by_role("button", 1))
    text = run(smart.emergency_read_by_text("Cancel", 0))

    assert b2.clicked is True
    assert text == "Cancel"


def test_smartwright_emergency_out_of_range(tmp_path: Path):
    page = FakePage([FakeElement(tag="input", text="", label="Email")])
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    try:
        run(smart.emergency_click("input", 3))
        assert False, "expected IndexError"
    except IndexError:
        assert True


def test_smartwright_emergency_click_first_input_containing(tmp_path: Path):
    i0 = FakeElement(tag="input", attrs={"placeholder": "search"})
    i1 = FakeElement(tag="input", attrs={"placeholder": "Send message"})
    page = FakePage([i0, i1])
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    run(smart.emergency_click_first_input_containing("send", humanized=False))
    assert i0.clicked is False
    assert i1.clicked is True


def test_smartwright_emergency_fill_first_type_containing(tmp_path: Path):
    t0 = FakeElement(tag="textarea", attrs={"placeholder": "Message"})
    t1 = FakeElement(tag="textarea", attrs={"placeholder": "Prompt"})
    page = FakePage([t0, t1])
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    run(smart.emergency_fill_first_type_containing("textarea", "prompt", "ola", humanized=False))
    assert t0.filled_value is None
    assert t1.filled_value == "ola"


def test_smartwright_wait_response_text_tracks_stream_until_stable(tmp_path: Path):
    page = FakeStreamingPage(
        [
            "",
            "Ola",
            "Ola, como posso ajudar?",
            "Ola, como posso ajudar hoje?",
            "Ola, como posso ajudar hoje?",
            "Ola, como posso ajudar hoje?",
            "Ola, como posso ajudar hoje?",
        ]
    )
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    text = run(smart.wait_response_text(timeout_ms=3000, stable_rounds=2, poll_interval_ms=100))
    assert text == "Ola, como posso ajudar hoje?"


def test_smartwright_wait_and_click_copy_button_waits_until_appears(tmp_path: Path):
    page = FakeCopyButtonPage(appear_after_polls=2)
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    ok = run(smart.wait_and_click_copy_button(timeout_ms=1500, poll_interval_ms=100))
    assert ok is True
    assert page.clicked is True


def test_smartwright_wait_and_click_copy_button_times_out(tmp_path: Path):
    page = FakeCopyButtonPage(appear_after_polls=999)
    rc = FakeRequestContext()
    smart = Smartwright(page=page, request_context=rc, store_path=str(tmp_path / "k.json"))

    ok = run(smart.wait_and_click_copy_button(timeout_ms=300, poll_interval_ms=100))
    assert ok is False
