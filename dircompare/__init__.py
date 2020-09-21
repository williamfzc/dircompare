# MIT License
#
# Copyright (c) 2020 williamfzc
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from dircompare._d2hc import file2snippet
from jinja2 import Template
from difile import Difile
import os
from collections import namedtuple
import pathlib
import tempfile
import typing

DEP_DIR = pathlib.Path(__file__).parent / "deps"
TEMPLATE_HTML = DEP_DIR / "template.html"
# assets
DIFF_JS = DEP_DIR / "diff.js"
DIFF_CSS = DEP_DIR / "diff.css"
RESET_CSS = DEP_DIR / "reset.css"
CODEFORMAT_CSS = DEP_DIR / "codeformats" / "xcode.css"

# types
TYPE_PATH = typing.Union[str, pathlib.Path]

# charset
CHARSET = "utf-8"


def _load_template() -> Template:
    with open(TEMPLATE_HTML, encoding=CHARSET) as f:
        content = f.read()
    return Template(content)


def compare(dir1: TYPE_PATH, dir2: TYPE_PATH, coverage_xml: TYPE_PATH = None) -> str:
    if isinstance(dir1, str):
        dir1 = pathlib.Path(dir1)
    if isinstance(dir2, str):
        dir2 = pathlib.Path(dir2)
    dir1, dir2 = dir1.absolute(), dir2.absolute()
    assert dir1.is_dir() and dir2.is_dir()

    if coverage_xml and isinstance(coverage_xml, str):
        coverage_xml = pathlib.Path(coverage_xml).absolute()
        assert coverage_xml.is_file()

    difile = Difile()
    diff_files = difile.compare_dir(dir1, dir2)

    # prune
    files = set()
    for each in diff_files:
        if not each:
            continue
        each_path = each[0].file_path
        try:
            after = each_path.relative_to(dir1)
        except ValueError:
            after = each_path.relative_to(dir2)
        files.add(after)

    # gen
    snippets = []
    Snippet = namedtuple("Snippet", ("name", "content"))
    for each in files:
        file1 = dir1 / each
        file2 = dir2 / each
        # special handle
        # i have to disable `delete` by default for some Windows issues
        with tempfile.NamedTemporaryFile(delete=False) as f:
            # file added
            if (not file1.is_file()) and file2.is_file():
                snippet_content = file2snippet(f.name, file2, dir2, coverage_xml)
            # file removed
            elif file1.is_file() and (not file2.is_file()):
                snippet_content = file2snippet(file1, f.name, dir2, coverage_xml)
            # normal
            else:
                snippet_content = file2snippet(file1, file2, dir2, coverage_xml)
            # remove temp file by myself
            f.close()
            os.remove(f.name)
        snippets.append(Snippet(each, snippet_content))

    # render
    template = _load_template()
    # read assets
    assets = dict()
    for k, v in {
        "diff_js": DIFF_JS,
        "diff_css": DIFF_CSS,
        "reset_css": RESET_CSS,
        "codeformats_css": CODEFORMAT_CSS,
    }.items():
        with open(v, encoding=CHARSET) as f:
            assets[k] = f.read()

    return template.render(files=snippets, **assets,)
