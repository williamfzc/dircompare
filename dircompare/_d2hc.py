# module for creating html snippet
# this file originally comes from https://github.com/wagoodman/diff2HtmlCompare
# thanks

# origin license:
# MIT License
#
# Copyright (c) 2016 Alex Goodman
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
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

import io
import sys
import difflib
import pygments
import functools
import pathlib
from pygments.lexers import guess_lexer_for_filename
from pygments.lexer import RegexLexer
from pygments.formatters import HtmlFormatter
from pygments.token import *
from collections import namedtuple
from diff_cover.violationsreporters.violations_reporter import XmlCoverageReporter
from diff_cover.git_path import GitPathTool

try:
    # Needed for Python < 3.3, works up to 3.8
    import xml.etree.cElementTree as etree
except ImportError:
    # Python 3.9 onwards
    import xml.etree.ElementTree as etree

# Monokai is not quite right yet
PYGMENTS_STYLES = ["vs", "xcode"]

HTML_TEMPLATE = """
<div class="" id="topbar">
  <div id="filetitle"> 
    %(page_title)s
  </div>
  <div class="switches">
    <div class="switch">
      <input id="showoriginal" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
      <label for="showoriginal" data-on="&#10004; Original" data-off="Original"></label>
    </div>
    <div class="switch">
      <input id="showmodified" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
      <label for="showmodified" data-on="&#10004; Modified" data-off="Modified"></label>
    </div>
    <div class="switch">
      <input id="highlight" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
      <label for="highlight" data-on="&#10004; Highlight" data-off="Highlight"></label>
    </div>
    <div class="switch">
      <input id="codeprintmargin" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
      <label for="codeprintmargin" data-on="&#10004; Margin" data-off="Margin"></label>
    </div>
    <div class="switch">
      <input id="dosyntaxhighlight" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
      <label for="dosyntaxhighlight" data-on="&#10004; Syntax" data-off="Syntax"></label>
    </div>
  </div>
</div>
<div id="maincontainer" class="%(page_width)s">
    <div id="leftcode" class="left-inner-shadow codebox divider-outside-bottom">
        <div class="codefiletab">
            &#10092; Original
        </div>
        <div class="printmargin">
            01234567890123456789012345678901234567890123456789012345678901234567890123456789
        </div>
        %(original_code)s
    </div>
    <div id="rightcode" class="left-inner-shadow codebox divider-outside-bottom">
        <div class="codefiletab">
            &#10093; Modified
        </div>
        <div class="printmargin">
            01234567890123456789012345678901234567890123456789012345678901234567890123456789
        </div>
        %(modified_code)s
    </div>
</div>
"""


@functools.lru_cache(None)
def _read_xml(xml_path):
    GitPathTool.set_cwd(None)
    return [etree.parse(xml_root) for xml_root in [xml_path]]


def coverage_xml_parse(xml_file_path, src_file_path, root):
    # type cast
    if isinstance(src_file_path, str):
        src_file_path = pathlib.Path(src_file_path)
    if isinstance(root, str):
        root = pathlib.Path(root)

    xml_roots = _read_xml(xml_file_path)
    coverage = XmlCoverageReporter(xml_roots, [root.as_posix(), ''])
    try:
        rel_src_file_path = src_file_path.relative_to(root).as_posix()
    except ValueError:
        # no rel src file found, skipped
        return
    coverage._cache_file(rel_src_file_path)
    return coverage._info_cache[rel_src_file_path]


coverage_line_list = None


class DefaultLexer(RegexLexer):
    """
    Simply lex each line as a token.
    """

    name = 'Default'
    aliases = ['default']
    filenames = ['*']

    tokens = {
        'root': [
            (r'.*\n', Text),
        ]
    }


class DiffHtmlFormatter(HtmlFormatter):
    """
    Formats a single source file with pygments and adds diff highlights based on the
    diff details given.
    """
    isLeft = False
    diffs = None

    def __init__(self, isLeft, diffs, line_filter=None, *args, **kwargs):
        self.isLeft = isLeft
        self.diffs = diffs
        self.line_filter = line_filter
        super(DiffHtmlFormatter, self).__init__(*args, **kwargs)

    def wrap(self, source, outfile):
        return self._wrap_code(source)

    def getDiffLineNos(self):
        retlinenos = []
        for idx, ((left_no, left_line), (right_no, right_line), change) in enumerate(self.diffs):
            no = None

            # no coverage xml, do not draw
            # None and [] is different here
            # coverage will only make sense in right side
            need_coverage_draw = bool(coverage_line_list and (coverage_line_list[1] is not None))
            coverage_class_miss = "lineno_coverage_miss"
            coverage_class_hit = "lineno_coverage_hit"

            if self.isLeft:
                if change:
                    if isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftchange">' + \
                            str(left_no) + "</span>"
                    elif isinstance(left_no, int) and not isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftdel">' + \
                            str(left_no) + "</span>"
                    elif not isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftadd">  </span>'
                else:
                    no = '<span class="lineno_q">' + str(left_no) + "</span>"
            else:
                # add coverage here
                if change:
                    if isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightchange {cov}">' + \
                            str(right_no) + "</span>"
                    elif isinstance(left_no, int) and not isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightdel {cov}">  </span>'
                    elif not isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightadd {cov}">' + \
                            str(right_no) + "</span>"
                else:
                    no = '<span class="lineno_q {cov}">' + str(right_no) + "</span>"

                # coverage
                if need_coverage_draw and change:
                    # coverage line list will not contain empty lines
                    # and something like function signature
                    content = right_line.strip()
                    if (not content) or content.startswith("#") or content.startswith("//"):
                        pass
                    elif self.line_filter and (right_no not in self.line_filter):
                        # ignore
                        pass
                    elif (right_no in coverage_line_list[1]) and (right_no not in coverage_line_list[0]):
                        no = no.format(cov=coverage_class_hit)
                    else:
                        no = no.format(cov=coverage_class_miss)

            retlinenos.append(no)

        return retlinenos

    def _wrap_code(self, source):
        source = list(source)
        yield 0, '<pre>'

        for idx, ((left_no, left_line), (right_no, right_line), change) in enumerate(self.diffs):
            # print idx, ((left_no, left_line),(right_no, right_line),change)
            try:
                if self.isLeft:
                    if change:
                        if isinstance(left_no, int) and isinstance(right_no, int) and left_no <= len(source):
                            i, t = source[left_no - 1]
                            t = '<span class="left_diff_change">' + t + "</span>"
                        elif isinstance(left_no, int) and not isinstance(right_no, int) and left_no <= len(source):
                            i, t = source[left_no - 1]
                            t = '<span class="left_diff_del">' + t + "</span>"
                        elif not isinstance(left_no, int) and isinstance(right_no, int):
                            i, t = 1, left_line
                            t = '<span class="left_diff_add">' + t + "</span>"
                        else:
                            raise
                    else:
                        if left_no <= len(source):
                            i, t = source[left_no - 1]
                        else:
                            i = 1
                            t = left_line
                else:
                    if change:
                        if isinstance(left_no, int) and isinstance(right_no, int) and right_no <= len(source):
                            i, t = source[right_no - 1]
                            t = '<span class="right_diff_change">' + t + "</span>"
                        elif isinstance(left_no, int) and not isinstance(right_no, int):
                            i, t = 1, right_line
                            t = '<span class="right_diff_del">' + t + "</span>"
                        elif not isinstance(left_no, int) and isinstance(right_no, int) and right_no <= len(source):
                            i, t = source[right_no - 1]
                            t = '<span class="right_diff_add">' + t + "</span>"
                        else:
                            raise
                    else:
                        if right_no <= len(source):
                            i, t = source[right_no - 1]
                        else:
                            i = 1
                            t = right_line
                yield i, t
            except:
                # print "WARNING! failed to enumerate diffs fully!"
                pass  # this is expected sometimes
        yield 0, '\n</pre>'

    def _wrap_tablelinenos(self, inner):
        dummyoutfile = io.StringIO()
        lncount = 0
        for t, line in inner:
            if t:
                lncount += 1

            # compatibility Python v2/v3
            if sys.version_info > (3,0):
                dummyoutfile.write(line)
            else:
                dummyoutfile.write(unicode(line))

        fl = self.linenostart
        mw = len(str(lncount + fl - 1))
        sp = self.linenospecial
        st = self.linenostep
        la = self.lineanchors
        aln = self.anchorlinenos
        nocls = self.noclasses

        lines = []
        for i in self.getDiffLineNos():
            lines.append('%s' % (i,))

        ls = ''.join(lines)

        # in case you wonder about the seemingly redundant <div> here: since the
        # content in the other cell also is wrapped in a div, some browsers in
        # some configurations seem to mess up the formatting...
        if nocls:
            yield 0, ('<table class="%stable">' % self.cssclass +
                      '<tr><td><div class="linenodiv" '
                      'style="background-color: #f0f0f0; padding-right: 10px">'
                      '<pre style="line-height: 125%">' +
                      ls + '</pre></div></td><td class="code">')
        else:
            yield 0, ('<table class="%stable">' % self.cssclass +
                      '<tr><td class="linenos"><div class="linenodiv"><pre>' +
                      ls + '</pre></div></td><td class="code">')
        yield 0, dummyoutfile.getvalue()
        yield 0, '</td></tr></table>'


class CodeDiff(object):
    """
    Manages a pair of source files and generates a single html diff page comparing
    the contents.
    """
    pygmentsCssFile = "./deps/codeformats/%s.css"
    diffCssFile = "./deps/diff.css"
    diffJsFile = "./deps/diff.js"
    resetCssFile = "./deps/reset.css"
    jqueryJsFile = "./deps/jquery.min.js"

    def __init__(self, fromfile, tofile, fromtxt=None, totxt=None, name=None):
        self.filename = name
        self.fromfile = fromfile
        if fromtxt == None:
            try:
                with io.open(fromfile, encoding="utf-8") as f:
                    self.fromlines = f.readlines()
            except Exception as e:
                print("Problem reading file %s" % fromfile)
                print(e)
                sys.exit(1)
        else:
            self.fromlines = [n + "\n" for n in fromtxt.split("\n")]
        self.leftcode = "".join(self.fromlines)

        self.tofile = tofile
        if totxt == None:
            try:
                with io.open(tofile, encoding="utf-8") as f:
                    self.tolines = f.readlines()
            except Exception as e:
                print("Problem reading file %s" % tofile)
                print(e)
                sys.exit(1)
        else:
            self.tolines = [n + "\n" for n in totxt.split("\n")]
        self.rightcode = "".join(self.tolines)

    def getDiffDetails(self, fromdesc='', todesc='', context=False, numlines=5, tabSize=8):
        # change tabs to spaces before it gets more difficult after we insert
        # markkup
        def expand_tabs(line):
            # hide real spaces
            line = line.replace(' ', '\0')
            # expand tabs into spaces
            line = line.expandtabs(tabSize)
            # replace spaces from expanded tabs back into tab characters
            # (we'll replace them with markup after we do differencing)
            line = line.replace(' ', '\t')
            return line.replace('\0', ' ').rstrip('\n')

        self.fromlines = [expand_tabs(line) for line in self.fromlines]
        self.tolines = [expand_tabs(line) for line in self.tolines]

        # create diffs iterator which generates side by side from/to data
        if context:
            context_lines = numlines
        else:
            context_lines = None

        diffs = difflib._mdiff(self.fromlines, self.tolines, context_lines,
                               linejunk=None, charjunk=difflib.IS_CHARACTER_JUNK)
        return list(diffs)

    def format(self, options):
        self.diffs = self.getDiffDetails(self.fromfile, self.tofile)

        if options.verbose:
            for diff in self.diffs:
                print("%-6s %-80s %-80s" % (diff[2], diff[0], diff[1]))

        fields = ((self.leftcode, True, self.fromfile),
                  (self.rightcode, False, self.tofile))

        codeContents = []
        for (code, isLeft, filename) in fields:

            inst = DiffHtmlFormatter(isLeft,
                                     self.diffs,
                                     nobackground=False,
                                     linenos=True,
                                     style=options.syntax_css,
                                     line_filter=options.line_filter,
                                     )

            try:
                self.lexer = guess_lexer_for_filename(self.filename, code)

            except pygments.util.ClassNotFound:
                if options.verbose:
                    print("No Lexer Found! Using default...")

                self.lexer = DefaultLexer()

            formatted = pygments.highlight(code, self.lexer, inst)

            codeContents.append(formatted)

        answers = {
            "html_title":     self.filename,
            "reset_css":      self.resetCssFile,
            "pygments_css":   self.pygmentsCssFile % options.syntax_css,
            "diff_css":       self.diffCssFile,
            "page_title":     self.filename,
            "original_code":  codeContents[0],
            "modified_code":  codeContents[1],
            "jquery_js":      self.jqueryJsFile,
            "diff_js":        self.diffJsFile,
            "page_width":     "page-80-width" if options.print_width else "page-full-width"
        }

        self.htmlContents = HTML_TEMPLATE % answers

    def write(self, path):
        fh = io.open(path, 'w', encoding="utf-8")
        fh.write(self.htmlContents)
        fh.close()


def file2snippet(file1, file2, root_dir=None, cobertura_xml=None, line_filter=None):
    if cobertura_xml:
        r = coverage_xml_parse(cobertura_xml, file2, root_dir)
        # it looks like:
        # ({9, 11}, {2, 4, 5, 6, 9, 11})
        # which means:
        # - all lines: {2, 4, 5, 6, 9, 11}
        # - missed: {9, 11}
        if r:
            global coverage_line_list
            coverage_line_list = ({each.line for each in r[0]}, r[1])

    # options
    Options = namedtuple("options", ("coverage", "file1", "file2", "output_path", "print_width", "show", "syntax_css", "verbose", "line_filter"))
    options = Options(
        cobertura_xml,
        file1,
        file2,
        None,
        False,
        False,
        "vs",
        False,
        line_filter,
    )

    codeDiff = CodeDiff(file1, file2, name=file2)
    codeDiff.format(options)
    return codeDiff.htmlContents
