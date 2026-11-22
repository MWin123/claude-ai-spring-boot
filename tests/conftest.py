"""Test log layout: emoji results (pytest-emoji) and, with -v, one block per test file.

In GitHub Actions each file block is a collapsible group; failures are repeated after their group.
The cases of a parametrized test share one heading, grouped by doc file where the ids are `path:line`.
"""

import os
import re
import textwrap
from collections import Counter
from typing import Any

import pytest
from _pytest.terminal import TerminalReporter

pytest_plugins = ["install_fixtures"]

ACTIONS = os.environ.get("GITHUB_ACTIONS") == "true"
type Markup = dict[str, bool]  # TerminalWriter colors, e.g. {"red": True}


def pytest_emoji_passed(config: pytest.Config) -> tuple[str, str]:
    return "✅ ", "✅"


def pytest_emoji_failed(config: pytest.Config) -> tuple[str, str]:
    return "❌ ", "❌"


def pytest_emoji_skipped(config: pytest.Config) -> tuple[str, str]:
    return "⏭️ ", "⏭️"


def pytest_emoji_error(config: pytest.Config) -> tuple[str, str]:
    return "💥 ", "💥"


def pytest_emoji_xfailed(config: pytest.Config) -> tuple[str, str]:
    return "🤷 ", "🤷"


def pytest_emoji_xpassed(config: pytest.Config) -> tuple[str, str]:
    return "😲 ", "😲"


def _results_line(self: TerminalReporter) -> None:
    """One line, passed first: `Results (1.41s): ✨ 324 passed | 3 failed | 12 skipped` (counts above zero)."""
    # sets start_time and end_time (ns) at session start and finish
    import pytest_pretty  # type: ignore[import-untyped]

    parts, _ = self.build_summary_stats_line()
    parts.sort(key=lambda part: not part[0].endswith(" passed"))
    seconds = (pytest_pretty.end_time - pytest_pretty.start_time) / 1e9
    self._tw.write(f"Results ({seconds:.2f}s):", bold=True)
    self._tw.write(" ✨ ")
    for i, (text, markup) in enumerate(parts):
        self._tw.write(" | " * (i > 0))
        self._tw.write(text, **markup)
    self._tw.line()


def _patch_pretty() -> None:
    """pytest-pretty pads every failed line with "[ NN%]", ignoring console_output_style,
    and prints its results as a block; replace it with one line."""
    try:
        from pytest_pretty import CustomTerminalReporter
    except ImportError:
        return
    CustomTerminalReporter._write_progress_information_filling_space = lambda self: None
    CustomTerminalReporter.summary_stats = _results_line


_patch_pretty()

PATH_LINE = re.compile(r"(.+):(\d+)")
INDENT = " " * 7


def _rank(markup: Markup) -> int:  # the result's color: red (failed, error), yellow (skipped, xfail, xpass), green
    return 0 if markup.get("red") else 1 if markup.get("yellow") else 2


def _mark(emoji: str, markup: Markup, text: str) -> str:
    # only results other than passed; the no-break space keeps them together
    return text if _rank(markup) == 2 else f"{emoji}\u00a0{text}"


class _FileBlocks:
    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.counts: Counter[str] = Counter()
        self.file: str | None = None
        self.failures: list[tuple[str, str]] = []  # (test name, first line of the error)
        self.test: str | None = None
        self.cases: list[list[Any]] = []  # [param, emoji, markup, reason] per case of self.test

    @property
    def reporter(self) -> TerminalReporter:  # looked up late: pytest-pretty swaps the reporter in pytest_configure
        reporter: TerminalReporter = self.config.pluginmanager.getplugin("terminalreporter")
        return reporter

    def _line(self, emoji: str, markup: Markup, text: str = "") -> None:
        """`  <emoji> <text>`, the emoji colored, wrapped with a hanging indent."""
        out = self.reporter._tw
        if out.width_of_current_line:  # pytest-pretty leaves its failure line open
            out.line()
        lines = textwrap.wrap(text, out.fullwidth - 5, subsequent_indent=INDENT[5:],
                              break_long_words=False, break_on_hyphens=False) or [""]
        out.write(f"  {emoji} ", **markup)
        out.line(lines[0])
        for rest in lines[1:]:
            out.line(f"     {rest}")
        self.reporter.currentfspath = None

    def result(self, name: str, emoji: str, markup: Markup) -> None:
        """One test result, written once the test changes: the cases of a parametrized test go together."""
        test, _, param = name.partition("[")
        if test != self.test or not param:
            self.flush()
        self.test = test
        self.cases.append([param[:-1], emoji, markup, ""])

    def reason(self, text: str) -> None:
        """The " (reason)" pytest writes after a skipped or xfail result; it belongs to the last case."""
        self.cases[-1][3] += text

    def flush(self) -> None:
        test, cases, self.test, self.cases = self.test, self.cases, None, []
        if not cases:
            return
        _, emoji, markup, _ = min(cases, key=lambda case: _rank(case[2]))
        if not cases[0][0]:  # not parametrized
            self._line(emoji, markup, test + cases[0][3])
            return
        heading = f"{test} ({len(cases)})"
        found = [match for case in cases if (match := PATH_LINE.fullmatch(case[0]))]
        if len(found) < len(cases):  # e.g. [pom.xml], [False]: all cases on the heading line
            self._line(emoji, markup, heading + ": " + ", ".join(_mark(e, m, p + r) for p, e, m, r in cases))
            return
        self._line(emoji, markup, heading)
        lines: dict[str, list[str]] = {}  # doc file -> its line numbers
        for match, (_, case_emoji, case_markup, why) in zip(found, cases):
            lines.setdefault(match[1], []).append(_mark(case_emoji, case_markup, f":{match[2]}{why}"))
        width = self.reporter._tw.fullwidth
        for path, numbers in lines.items():
            for line in textwrap.wrap(f"{path} {' '.join(numbers)}", width - len(INDENT),
                                      subsequent_indent=" " * (len(path) + 1),
                                      break_long_words=False, break_on_hyphens=False):
                self.reporter._tw.line(INDENT + line)

    def close(self) -> None:
        if self.file is None:
            return
        self.flush()
        out = self.reporter._tw
        if out.width_of_current_line:
            out.line()
        if ACTIONS:
            out.line("::endgroup::")
        for name, message in self.failures:
            out.line(f"❌ {self.file}::{name}: {message}", red=True)
        self.failures = []

    @pytest.hookimpl(trylast=True)
    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.counts = Counter(item.location[0] for item in session.items)

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_logstart(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        if location[0] == self.file:
            return
        self.reporter.ensure_newline()
        self.close()
        self.file = location[0]
        count = self.counts[self.file]
        heading = f"{self.file} ({count} test{'s' * (count != 1)})"
        if ACTIONS:  # a workflow command must start the line, so no color codes
            self.reporter._tw.line(f"::group::{heading}")
        else:
            self.reporter._tw.line(heading, bold=True)

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.failed:
            crash = getattr(report.longrepr, "reprcrash", None)
            message = crash.message.splitlines()[0] if crash and crash.message else report.when
            self.failures.append((report.nodeid.split("::", 1)[-1], message))

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionfinish(self) -> None:
        self.reporter.ensure_newline()
        self.close()


@pytest.hookimpl(trylast=True)
def pytest_configure(config: pytest.Config) -> None:
    if config.get_verbosity() < 1 or config.pluginmanager.getplugin("terminalreporter") is None:
        return
    blocks = _FileBlocks(config)

    def write_ensure_prefix(self: TerminalReporter, prefix: str, extra: str = "", **markup: bool) -> None:
        if extra:  # called again with the result; the call at test start writes nothing
            # the -v line without its file part (the file is the block heading)
            blocks.result(prefix.split("::", 1)[-1].strip(), extra.strip(), markup)

    def wrap_write(self: TerminalReporter, content: str, **markup: Any) -> None:
        # pytest's only use: the skip reason after a result
        blocks.reason(content)

    TerminalReporter.write_ensure_prefix = write_ensure_prefix  # type: ignore[method-assign]
    TerminalReporter.wrap_write = wrap_write  # type: ignore[method-assign]
    config.pluginmanager.register(blocks, "file-blocks")
