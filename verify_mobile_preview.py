from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
DEFAULT_HTML = ROOT / "preview-RalstA6VgG32cRnj" / "index.html"
DEFAULT_LIVE = "https://garettwong.github.io/site-lab-472e3fb9/preview-RalstA6VgG32cRnj/"
AUDIT_DIR = ROOT / "audit"


@dataclass
class CheckReport:
    passes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    metrics: dict[str, object] = field(default_factory=dict)

    def ok(self, msg: str) -> None:
        self.passes.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)

    @property
    def success(self) -> bool:
        return not self.failures


def read_text_source(source: str, report: CheckReport, label: str) -> str:
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={"User-Agent": "HermesMobilePreviewGate/1.0"})
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode("utf-8", "ignore")
            ctype = response.headers.get("content-type", "")
            report.ok(f"{label}: HTTP {response.status}, {len(body.encode('utf-8'))} bytes, {ctype}")
            return body
    path = pathlib.Path(source)
    body = path.read_text(encoding="utf-8", errors="ignore")
    report.ok(f"{label}: read {path}, {len(body.encode('utf-8'))} bytes")
    return body


def strip_hash(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def build_route_url(base: str, route: str, html_path: pathlib.Path | None = None) -> str:
    route = route.lstrip("#")
    if base == "file":
        assert html_path is not None
        return html_path.resolve().as_uri() + f"#{route}"
    return strip_hash(base).rstrip("/") + f"/#{route}"


def extract_inline_script(html: str) -> str:
    scripts = re.findall(r"<script[^>]*>([\s\S]*?)</script>", html, flags=re.I)
    return "\n\n".join(scripts)


def extract_style(html: str) -> str:
    styles = re.findall(r"<style[^>]*>([\s\S]*?)</style>", html, flags=re.I)
    return "\n\n".join(styles)


def declaration_contains_opacity(decl: str, value: str) -> bool:
    return re.search(rf"opacity\s*:\s*{re.escape(value)}\b", decl) is not None


def check_static_contract(html: str, report: CheckReport, label: str) -> None:
    style = extract_style(html)
    script = extract_inline_script(html)

    if "<meta name=\"viewport\"" in html or "<meta name='viewport'" in html:
        report.ok(f"{label}: viewport meta present")
    else:
        report.fail(f"{label}: viewport meta missing")

    if "noindex,nofollow,noarchive" in html:
        report.ok(f"{label}: noindex/nofollow/noarchive present")
    else:
        report.fail(f"{label}: noindex/nofollow/noarchive missing")

    # The regression Garett saw was caused by fail-closed reveal CSS: all sections
    # began opacity:0, then a JS initialization error prevented .in from being added.
    default_reveal_blocks = re.findall(r"(?:^|})\s*\.reveal\s*\{([^}]*)\}", style)
    motion_reveal_blocks = re.findall(r"\.motion-ready\s+\.reveal\s*\{([^}]*)\}", style)
    default_hidden = any(declaration_contains_opacity(block, "0") for block in default_reveal_blocks)
    default_visible = any(declaration_contains_opacity(block, "1") for block in default_reveal_blocks)
    motion_hides = any(declaration_contains_opacity(block, "0") for block in motion_reveal_blocks)
    report.metrics[f"{label}.default_reveal_blocks"] = len(default_reveal_blocks)
    report.metrics[f"{label}.motion_reveal_blocks"] = len(motion_reveal_blocks)
    if default_hidden:
        report.fail(f"{label}: .reveal is hidden by default; page can go blank if JS fails")
    elif default_visible and motion_hides:
        report.ok(f"{label}: reveal animation is fail-open (visible by default, hidden only after motion-ready)")
    elif default_reveal_blocks:
        report.warn(f"{label}: reveal CSS found but fail-open pattern was not explicit")
    else:
        report.warn(f"{label}: no .reveal CSS blocks found")

    if 'class="primary"' in html or "class='primary'" in html:
        report.fail(f"{label}: hard-coded primary nav class found; active tab can be wrong before router runs")
    else:
        report.ok(f"{label}: no hard-coded primary nav class")

    if 'href="#/' in html or "href='#/" in html:
        report.fail(f"{label}: slash-hash links (#/route) found; use #route so browser anchors and router agree")
    else:
        report.ok(f"{label}: route links use canonical #route anchors")

    route_idx = script.find("const routeMap=")
    nav_idx = script.find("const navLinks=")
    set_lang_idx = script.find("try{setLang")
    if set_lang_idx != -1 and (route_idx == -1 or nav_idx == -1 or set_lang_idx < route_idx or set_lang_idx < nav_idx):
        report.fail(f"{label}: setLang initializer appears before route/nav declarations; this can throw at startup")
    else:
        report.ok(f"{label}: language/router initialization order is safe")

    if "data-lang=\"en\"" in html and "data-lang=\"zh\"" in html:
        report.ok(f"{label}: EN/繁 language buttons present")
    else:
        report.warn(f"{label}: expected EN/繁 language buttons not found")

    if "border-radius:0!important" in html:
        report.ok(f"{label}: straight-corner marker present")
    else:
        report.warn(f"{label}: straight-corner marker missing")

    if script.strip():
        check_node_syntax(script, report, label)
    else:
        report.warn(f"{label}: no inline script found for syntax check")


def check_node_syntax(script: str, report: CheckReport, label: str) -> None:
    node = shutil.which("node")
    if not node:
        report.fail(f"{label}: node not found; cannot syntax-check browser script")
        return
    tmp = tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8")
    try:
        tmp.write(script)
        tmp.close()
        result = subprocess.run([node, "--check", tmp.name], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        if result.returncode == 0:
            report.ok(f"{label}: node --check passed")
        else:
            report.fail(f"{label}: node --check failed: {result.stdout.strip()[:500]}")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def find_edge() -> pathlib.Path | None:
    env = os.environ.get("EDGE_BIN")
    candidates = []
    if env:
        candidates.append(pathlib.Path(env))
    candidates.extend([
        pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        pathlib.Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        pathlib.Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        pathlib.Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def screenshot_with_browser(url: str, output: pathlib.Path, report: CheckReport, label: str) -> None:
    browser = find_edge()
    if not browser:
        report.fail(f"{label}: no Edge/Chrome browser found; mobile screenshot gate cannot run")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(browser),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--window-size=390,844",
        "--force-device-scale-factor=1",
        "--virtual-time-budget=2500",
        f"--screenshot={output}",
        url,
    ]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    if result.returncode != 0 or not output.exists() or output.stat().st_size < 5000:
        report.fail(f"{label}: browser screenshot failed rc={result.returncode}: {result.stdout[-800:]}")
        return
    report.ok(f"{label}: screenshot captured {output} ({output.stat().st_size} bytes)")


def analyze_screenshot(path: pathlib.Path, report: CheckReport, label: str) -> None:
    img = Image.open(path).convert("RGB")
    width, height = img.size
    if width < 380 or height < 800:
        report.fail(f"{label}: screenshot size too small: {width}x{height}")
        return
    # Ignore sticky header and bottom private label. Blank-regression content area
    # was mostly cream after the header because the reveal sections stayed invisible.
    crop = img.crop((0, 130, width, max(131, height - 70)))
    total = crop.width * crop.height
    dark = 0
    very_dark = 0
    non_background = 0
    pixel_at = crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            r, g, b = pixel_at[x, y]
            lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
            if lum < 150:
                dark += 1
            if lum < 90:
                very_dark += 1
            if not (r > 235 and g > 220 and b > 175):
                non_background += 1
    dark_ratio = dark / total
    very_dark_ratio = very_dark / total
    non_bg_ratio = non_background / total
    report.metrics[f"{label}.screenshot_size"] = [width, height]
    report.metrics[f"{label}.dark_ratio"] = round(dark_ratio, 4)
    report.metrics[f"{label}.very_dark_ratio"] = round(very_dark_ratio, 4)
    report.metrics[f"{label}.non_background_ratio"] = round(non_bg_ratio, 4)
    if dark_ratio < 0.012 or non_bg_ratio < 0.035:
        report.fail(
            f"{label}: screenshot content area looks blank/near-blank "
            f"(dark_ratio={dark_ratio:.4f}, non_background_ratio={non_bg_ratio:.4f})"
        )
    else:
        report.ok(
            f"{label}: screenshot content area is visibly populated "
            f"(dark_ratio={dark_ratio:.4f}, non_background_ratio={non_bg_ratio:.4f})"
        )


def run_screenshot_gate(base: str, report: CheckReport, prefix: str, html_path: pathlib.Path | None = None) -> None:
    for route in ("home", "search"):
        url = build_route_url(base, route, html_path=html_path)
        out = AUDIT_DIR / f"mobile-gate-{prefix}-{route}.png"
        label = f"{prefix} #{route}"
        screenshot_with_browser(url, out, report, label)
        if out.exists():
            analyze_screenshot(out, report, label)


def write_json_report(report: CheckReport) -> pathlib.Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "mobile_preview_gate.json"
    payload = {
        "success": report.success,
        "passes": report.passes,
        "warnings": report.warnings,
        "failures": report.failures,
        "metrics": report.metrics,
        "written_at_epoch": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fail-fast mobile/JS visual gate for the maid-agency preview.")
    parser.add_argument("--html", default=str(DEFAULT_HTML), help="Local HTML file to statically check")
    parser.add_argument("--live", default=DEFAULT_LIVE, help="Live preview base URL to check; pass empty string to skip")
    parser.add_argument("--skip-browser", action="store_true", help="Skip mobile screenshot gate")
    parser.add_argument("--local-screenshot", action="store_true", help="Also screenshot the local file:// preview")
    args = parser.parse_args(argv)

    report = CheckReport()
    html_path = pathlib.Path(args.html)

    local_html = read_text_source(str(html_path), report, "local html")
    check_static_contract(local_html, report, "local html")

    live_base = args.live.strip()
    if live_base:
        live_html = read_text_source(strip_hash(live_base), report, "live html")
        check_static_contract(live_html, report, "live html")

    if not args.skip_browser:
        if args.local_screenshot:
            run_screenshot_gate("file", report, "local", html_path=html_path)
        if live_base:
            run_screenshot_gate(live_base, report, "live")

    json_path = write_json_report(report)
    print(f"Mobile preview gate: {'PASS' if report.success else 'FAIL'}")
    print(f"JSON report: {json_path}")
    for msg in report.passes:
        print(f"PASS: {msg}")
    for msg in report.warnings:
        print(f"WARN: {msg}")
    for msg in report.failures:
        print(f"FAIL: {msg}")
    if report.metrics:
        print("METRICS:")
        for key, value in sorted(report.metrics.items()):
            print(f"  {key}: {value}")
    return 0 if report.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
