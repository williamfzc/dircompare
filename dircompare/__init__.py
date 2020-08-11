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

__PROJECT_NAME__ = r"dircompare"
__AUTHOR__ = r"williamfzc"
__AUTHOR_EMAIL__ = r"fengzc@vip.qq.com"
__LICENSE__ = r"MIT"
__URL__ = r"https://github.com/williamfzc/dircompare"
__VERSION__ = r"0.1.0"
__DESCRIPTION__ = r"compare dir and generate a html report"


from dircompare._d2hc import file2snippet
from jinja2 import Template
from difile import Difile
import os
from collections import namedtuple
import pathlib
import tempfile

DEP_DIR = pathlib.Path(__file__).parent / "deps"
TEMPLATE_HTML = DEP_DIR / "template.html"
# assets
DIFF_JS = DEP_DIR / "diff.js"
DIFF_CSS = DEP_DIR / "diff.css"
RESET_CSS = DEP_DIR / "reset.css"
CODEFORMAT_CSS = DEP_DIR / "codeformats" / "xcode.css"


def _load_template() -> Template:
    with open(TEMPLATE_HTML, encoding="utf-8") as f:
        content = f.read()
    return Template(content)


def compare(dir1, dir2, coverage_xml=None) -> str:
    difile = Difile()
    diff_files = difile.compare_dir(dir1, dir2)

    # prune
    files = set()
    for each in diff_files:
        each_path = each[0].file_path
        after = os.sep.join(each_path.parts[1:])
        files.add(after)

    # gen
    snippets = []
    Snippet = namedtuple("Snippet", ("name", "content"))
    for each in files:
        file1 = os.path.join(dir1, each)
        file2 = os.path.join(dir2, each)
        # special handle
        with tempfile.NamedTemporaryFile() as f:
            # file added
            if (not os.path.isfile(file1)) and os.path.isfile(file2):
                snippet_content = file2snippet(f.name, file2, coverage_xml)
            # file removed
            elif os.path.isfile(file1) and (not os.path.isfile(file2)):
                snippet_content = file2snippet(file1, f.name, coverage_xml)
            # normal
            else:
                snippet_content = file2snippet(file1, file2, coverage_xml)
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
        with open(v, encoding="utf-8") as f:
            assets[k] = f.read()

    return template.render(
        files=snippets,
        **assets,
    )
