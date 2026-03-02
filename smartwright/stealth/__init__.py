"""Stealth / anti-detection layer for Playwright browsers.

Usage::

    from smartwright.stealth import StealthConfig, apply_stealth, get_stealth_args

    cfg = StealthConfig()                     # defaults: all protections ON
    cfg = StealthConfig(webgl=False)          # disable specific protections
    cfg = StealthConfig.minimal()             # only the essentials
    cfg = StealthConfig.maximum()             # everything + random profile

    # 1. Launch browser with stealth args
    browser = await p.chromium.launch(
        args=get_stealth_args(cfg),
        ignore_default_args=["--enable-automation"],
    )

    # 2. Apply JS injections to context
    context = await browser.new_context(**get_context_options(cfg))
    await apply_stealth(context, cfg)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


# ── Fingerprint profiles (consistent UA + platform + viewport + timezone) ──

PROFILES: list[dict[str, Any]] = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "platform": "Win32",
        "languages": ["en-US", "en"],
        "viewport": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "timezone": "America/New_York",
        "locale": "en-US",
        "hardware_concurrency": 8,
        "device_memory": 8,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.6723.91 Safari/537.36",
        "platform": "Win32",
        "languages": ["en-US", "en"],
        "viewport": {"width": 1366, "height": 768},
        "device_scale_factor": 1,
        "timezone": "America/Chicago",
        "locale": "en-US",
        "hardware_concurrency": 4,
        "device_memory": 8,
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "languages": ["en-US", "en"],
        "viewport": {"width": 1440, "height": 900},
        "device_scale_factor": 2,
        "timezone": "America/Los_Angeles",
        "locale": "en-US",
        "hardware_concurrency": 10,
        "device_memory": 16,
        "webgl_vendor": "Apple",
        "webgl_renderer": "Apple M1 Pro",
    },
    {
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "platform": "Linux x86_64",
        "languages": ["en-US", "en"],
        "viewport": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "timezone": "Europe/London",
        "locale": "en-GB",
        "hardware_concurrency": 8,
        "device_memory": 16,
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1080 Ti, OpenGL 4.5)",
    },
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "platform": "Win32",
        "languages": ["pt-BR", "pt", "en"],
        "viewport": {"width": 1920, "height": 1080},
        "device_scale_factor": 1,
        "timezone": "America/Sao_Paulo",
        "locale": "pt-BR",
        "hardware_concurrency": 8,
        "device_memory": 16,
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 580, Direct3D11 vs_5_0 ps_5_0, D3D11)",
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "platform": "MacIntel",
        "languages": ["es-ES", "es", "en"],
        "viewport": {"width": 2560, "height": 1440},
        "device_scale_factor": 2,
        "timezone": "Europe/Madrid",
        "locale": "es-ES",
        "hardware_concurrency": 12,
        "device_memory": 32,
        "webgl_vendor": "Apple",
        "webgl_renderer": "Apple M2 Max",
    },
]


@dataclass
class StealthConfig:
    """Configuration for stealth/anti-detection features."""

    # ── Toggle individual protections ──
    webdriver: bool = True          # Spoof navigator.webdriver → undefined
    plugins: bool = True            # Fake navigator.plugins/mimeTypes
    chrome_object: bool = True      # Fake window.chrome runtime
    permissions: bool = True        # Fix navigator.permissions.query
    hardware: bool = True           # Spoof hardwareConcurrency, deviceMemory, platform
    webgl: bool = True              # Spoof WebGL vendor/renderer
    canvas: bool = True             # Add noise to canvas fingerprint
    audio: bool = True              # Add noise to audio fingerprint
    connection: bool = True         # Fake navigator.connection
    webrtc: bool = True             # Prevent WebRTC IP leak

    # ── Browser launch options ──
    disable_automation: bool = True       # Remove --enable-automation flag
    disable_blink_features: bool = True   # --disable-blink-features=AutomationControlled
    disable_infobars: bool = True         # Hide "controlled by automation" bar
    no_sandbox: bool = False              # --no-sandbox (needed in some envs)

    # ── Fingerprint profile ──
    profile: dict[str, Any] | None = None   # Use specific profile (None = random)

    # ── Custom user agent ──
    user_agent: str | None = None         # Override profile UA (None = from profile)

    # ── Extra chromium args ──
    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def minimal(cls) -> StealthConfig:
        """Only essential protections: webdriver + automation flags."""
        return cls(
            plugins=False, chrome_object=False, permissions=False,
            hardware=False, webgl=False, canvas=False, audio=False,
            connection=False, webrtc=False,
        )

    @classmethod
    def maximum(cls) -> StealthConfig:
        """All protections enabled with random profile."""
        return cls()

    def get_profile(self) -> dict[str, Any]:
        """Get the fingerprint profile (specific or random)."""
        if self.profile:
            return self.profile
        return random.choice(PROFILES)


# ── Chromium launch args ────────────────────────────────────────────────

def get_stealth_args(config: StealthConfig | None = None) -> list[str]:
    """Return chromium launch args for stealth mode."""
    if config is None:
        config = StealthConfig()

    args: list[str] = ["--start-maximized"]

    if config.disable_blink_features:
        args.append("--disable-blink-features=AutomationControlled")
    if config.disable_infobars:
        args.append("--disable-infobars")
    if config.no_sandbox:
        args.append("--no-sandbox")

    args.extend([
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
        "--disable-hang-monitor",
        "--disable-popup-blocking",
        "--disable-prompt-on-repost",
        "--disable-sync",
        "--disable-translate",
        "--disable-background-networking",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--metrics-recording-only",
        "--enable-webgl",
    ])

    args.extend(config.extra_args)
    return args


def get_ignored_default_args(config: StealthConfig | None = None) -> list[str]:
    """Return default args to ignore (remove --enable-automation)."""
    if config is None:
        config = StealthConfig()
    if config.disable_automation:
        return ["--enable-automation"]
    return []


# ── Context options ─────────────────────────────────────────────────────

def get_context_options(config: StealthConfig | None = None) -> dict[str, Any]:
    """Return Playwright context options with fingerprint profile."""
    if config is None:
        config = StealthConfig()

    profile = config.get_profile()
    ua = config.user_agent or profile.get("user_agent", "")

    opts: dict[str, Any] = {"no_viewport": True}
    if ua:
        opts["user_agent"] = ua
    if profile.get("viewport"):
        opts["viewport"] = profile["viewport"]
        opts.pop("no_viewport", None)
    if profile.get("device_scale_factor"):
        opts["device_scale_factor"] = profile["device_scale_factor"]
    if profile.get("locale"):
        opts["locale"] = profile["locale"]
    if profile.get("timezone"):
        opts["timezone_id"] = profile["timezone"]

    return opts


# ── JavaScript injections ───────────────────────────────────────────────

def _js_webdriver() -> str:
    return """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
"""


def _js_plugins() -> str:
    return """
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        {name:"Chrome PDF Plugin",filename:"internal-pdf-viewer",description:"Portable Document Format",length:1},
        {name:"Chrome PDF Viewer",filename:"mhjfbmdgcfjbbpaeojofohoefgiehjai",description:"",length:1},
        {name:"Native Client",filename:"internal-nacl-plugin",description:"",length:2},
    ],
});
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => [
        {type:"application/pdf",suffixes:"pdf",description:"",enabledPlugin:navigator.plugins[0]},
        {type:"application/x-google-chrome-pdf",suffixes:"pdf",description:"Portable Document Format",enabledPlugin:navigator.plugins[1]},
    ],
});
"""


def _js_chrome_object() -> str:
    return """
window.chrome = window.chrome || {};
window.chrome.app = {isInstalled:false,InstallState:{DISABLED:'disabled',INSTALLED:'installed',NOT_INSTALLED:'not_installed'},RunningState:{CANNOT_RUN:'cannot_run',READY_TO_RUN:'ready_to_run',RUNNING:'running'}};
window.chrome.runtime = {OnInstalledReason:{CHROME_UPDATE:'chrome_update',INSTALL:'install',SHARED_MODULE_UPDATE:'shared_module_update',UPDATE:'update'},OnRestartRequiredReason:{APP_UPDATE:'app_update',OS_UPDATE:'os_update',PERIODIC:'periodic'},PlatformArch:{ARM:'arm',MIPS:'mips',MIPS64:'mips64',X86_32:'x86-32',X86_64:'x86-64'},PlatformOs:{ANDROID:'android',CROS:'cros',LINUX:'linux',MAC:'mac',OPENBSD:'openbsd',WIN:'win'},RequestUpdateCheckStatus:{NO_UPDATE:'no_update',THROTTLED:'throttled',UPDATE_AVAILABLE:'update_available'}};
"""


def _js_permissions() -> str:
    return """
const _origPermQuery = navigator.permissions.query.bind(navigator.permissions);
navigator.permissions.query = (p) =>
    p.name === 'notifications'
        ? Promise.resolve({state: Notification.permission})
        : _origPermQuery(p);
"""


def _js_hardware(profile: dict[str, Any]) -> str:
    platform = profile.get("platform", "Win32")
    languages = profile.get("languages", ["en-US", "en"])
    hw_conc = profile.get("hardware_concurrency", 8)
    dev_mem = profile.get("device_memory", 8)
    return f"""
Object.defineProperty(navigator, 'platform', {{ get: () => '{platform}' }});
Object.defineProperty(navigator, 'languages', {{ get: () => {languages} }});
Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hw_conc} }});
Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {dev_mem} }});
"""


def _js_connection() -> str:
    return """
Object.defineProperty(navigator, 'connection', {
    get: () => ({rtt:50,downlink:10,effectiveType:'4g',saveData:false})
});
"""


def _js_webgl(profile: dict[str, Any]) -> str:
    vendor = profile.get("webgl_vendor", "Google Inc. (NVIDIA)")
    renderer = profile.get("webgl_renderer", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)")
    return f"""
(function() {{
    const _spoof = function(proto) {{
        const orig = proto.getParameter;
        proto.getParameter = function(p) {{
            if (p === 37445) return '{vendor}';
            if (p === 37446) return '{renderer}';
            return orig.call(this, p);
        }};
    }};
    if (typeof WebGLRenderingContext !== 'undefined') _spoof(WebGLRenderingContext.prototype);
    if (typeof WebGL2RenderingContext !== 'undefined') _spoof(WebGL2RenderingContext.prototype);
}})();
"""


def _js_canvas() -> str:
    return """
(function() {
    const _origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, ...args) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const d = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < d.data.length; i += 4)
                    d.data[i] ^= (Math.random() > 0.5 ? 1 : 0);
                ctx.putImageData(d, 0, 0);
            } catch(e) {}
        }
        return _origToDataURL.apply(this, [type, ...args]);
    };
    const _origToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(cb, type, q) {
        const ctx = this.getContext('2d');
        if (ctx && this.width > 0 && this.height > 0) {
            try {
                const d = ctx.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < d.data.length; i += 4)
                    d.data[i] ^= (Math.random() > 0.5 ? 1 : 0);
                ctx.putImageData(d, 0, 0);
            } catch(e) {}
        }
        return _origToBlob.apply(this, [cb, type, q]);
    };
})();
"""


def _js_audio() -> str:
    return """
(function() {
    if (typeof AnalyserNode !== 'undefined') {
        const _origFloat = AnalyserNode.prototype.getFloatFrequencyData;
        AnalyserNode.prototype.getFloatFrequencyData = function(a) {
            _origFloat.call(this, a);
            for (let i = 0; i < a.length; i++) a[i] += (Math.random()*0.1-0.05);
        };
    }
    if (typeof AudioBuffer !== 'undefined') {
        const _origCh = AudioBuffer.prototype.getChannelData;
        AudioBuffer.prototype.getChannelData = function(ch) {
            const d = _origCh.call(this, ch);
            for (let i = 0; i < d.length; i++) d[i] += (Math.random()*0.0001-0.00005);
            return d;
        };
    }
})();
"""


def _js_webrtc() -> str:
    return """
(function() {
    if (typeof RTCPeerConnection !== 'undefined') {
        const _Orig = RTCPeerConnection;
        window.RTCPeerConnection = function(cfg, constraints) {
            if (cfg && cfg.iceServers) cfg.iceServers = [];
            return new _Orig(cfg, constraints);
        };
        window.RTCPeerConnection.prototype = _Orig.prototype;
    }
})();
"""


def build_stealth_js(config: StealthConfig | None = None) -> str:
    """Build the combined stealth JS injection script."""
    if config is None:
        config = StealthConfig()

    profile = config.get_profile()
    parts: list[str] = []

    if config.webdriver:
        parts.append(_js_webdriver())
    if config.plugins:
        parts.append(_js_plugins())
    if config.chrome_object:
        parts.append(_js_chrome_object())
    if config.permissions:
        parts.append(_js_permissions())
    if config.hardware:
        parts.append(_js_hardware(profile))
    if config.connection:
        parts.append(_js_connection())
    if config.webgl:
        parts.append(_js_webgl(profile))
    if config.canvas:
        parts.append(_js_canvas())
    if config.audio:
        parts.append(_js_audio())
    if config.webrtc:
        parts.append(_js_webrtc())

    return "\n".join(parts)


# ── Apply to context ────────────────────────────────────────────────────

async def apply_stealth(context: Any, config: StealthConfig | None = None) -> None:
    """Apply all stealth JS injections to a Playwright BrowserContext.

    Call this BEFORE navigating to any page::

        context = await browser.new_context(**get_context_options(cfg))
        await apply_stealth(context, cfg)
        page = await context.new_page()
    """
    js = build_stealth_js(config)
    if js.strip():
        await context.add_init_script(js)


async def apply_stealth_to_page(page: Any, config: StealthConfig | None = None) -> None:
    """Apply stealth JS directly to an already-open page.

    Use this when you don't control context creation (e.g., persistent context).
    Less reliable than apply_stealth() since it runs after page scripts.
    """
    js = build_stealth_js(config)
    if js.strip():
        await page.evaluate(js)
