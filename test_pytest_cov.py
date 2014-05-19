"""Tests for pytest-cov.

Known issues:

- If py 2 then can have tx for any py 2, but problems if tx for py 3.

- If py 3.0 then can have tx for py 3.0 / 3.1, but problems if tx for py 2.

- If py 3.1 then can have tx for py 3.1, but problems if tx for py 2 or py 3.0.

- For py 3.0 coverage seems to give incorrect results, it reports all
  covered except the one line which it should have actually covered.
  Issue reported upstream, also only problem with pass statement and
  is fine with simple assignment statement.
"""

import os
import sys

import virtualenv

import py


pytest_plugins = 'pytester', 'cov'

SCRIPT = '''
import sys

def pytest_generate_tests(metafunc):
    for i in range(10):
        metafunc.addcall()

def test_foo():
    assert True
    if sys.version_info[0] > 5:
        assert False
'''

SCRIPT_CHILD = '''
import sys

idx = int(sys.argv[1])

if idx == 0:
    pass
if idx == 1:
    pass
'''

SCRIPT_PARENT = '''
import subprocess
import sys

def pytest_generate_tests(metafunc):
    for i in range(2):
        metafunc.addcall(funcargs=dict(idx=i))

def test_foo(idx):
    out, err = subprocess.Popen(
        [sys.executable, 'child_script.py', str(idx)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE).communicate()

# there is a issue in coverage.py with multiline statements at
# end of file: https://bitbucket.org/ned/coveragepy/issue/293
pass
'''

SCRIPT_FUNCARG = '''
import coverage

def test_foo(cov):
    assert isinstance(cov, coverage.control.coverage)
'''

SCRIPT_FUNCARG_NOT_ACTIVE = '''
def test_foo(cov):
    assert cov is None
'''

MULTIPROCESSING_SCRIPT = '''
import multiprocessing

def target_fn():
    a = True
    return a

def test_run_target():
    p = multiprocessing.Process(target=target_fn)
    p.start()
    p.join()
'''


SCRIPT_FAIL = '''
def test_fail():
    assert False

'''

SCRIPT_RESULT = '8 * 88%'
CHILD_SCRIPT_RESULT = '6 * 100%'
PARENT_SCRIPT_RESULT = '8 * 100%'


def test_central(testdir):
    script = testdir.makepyfile(SCRIPT)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_central * %s *' % SCRIPT_RESULT,
        '*10 passed*'
        ])
    assert result.ret == 0


def test_ignore_coverage_fail_under_option_when_not_html_report(testdir):
    script = testdir.makepyfile(SCRIPT)

    required_coverage = 100
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-fail-under=%s' % required_coverage,
                               '--cov-report=term-missing',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_ignore_coverage_fail_under_option_when_not_html_report * %s *' % SCRIPT_RESULT,
        '*10 passed*'
        ])
    assert result.ret == 0


def test_return_failure_when_coverage_under_the_required(testdir):
    script = testdir.makepyfile(SCRIPT)

    required_coverage = 100
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-fail-under=%s' % required_coverage,
                               '--cov-report=html',
                               script)

    assert result.ret == 2
    result.stdout.fnmatch_lines([
        'Coverage(87.5%) is lower than the required({}%)!'.format(required_coverage)
    ])


def test_return_ok_when_coverage_above_the_required(testdir):
    script = testdir.makepyfile(SCRIPT)

    required_coverage = 50
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-fail-under=%s' % required_coverage,
                               '--cov-report=html',
                               script)

    assert result.ret == 0
    result.stdout.fnmatch_lines([
        'Coverage(87.5%) is higher than the required({}%).'.format(required_coverage)
    ])


def test_no_cov_on_fail(testdir):
    script = testdir.makepyfile(SCRIPT_FAIL)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '--no-cov-on-fail',
                               script)

    assert 'coverage: platform' not in result.stdout.str()
    result.stdout.fnmatch_lines(['*1 failed*'])
    assert result.ret == 1


def test_dist_collocated(testdir):
    script = testdir.makepyfile(SCRIPT)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=2*popen',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_dist_collocated * %s *' % SCRIPT_RESULT,
        '*10 passed*'
        ])
    assert result.ret == 0


def test_dist_not_collocated(testdir):
    script = testdir.makepyfile(SCRIPT)
    dir1 = testdir.mkdir('dir1')
    dir2 = testdir.mkdir('dir2')

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=popen//chdir=%s' % dir1,
                               '--tx=popen//chdir=%s' % dir2,
                               '--rsyncdir=%s' % script.basename,
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_dist_not_collocated * %s *' % SCRIPT_RESULT,
        '*10 passed*'
        ])
    assert result.ret == 0


def test_central_subprocess(testdir):
    scripts = testdir.makepyfile(parent_script=SCRIPT_PARENT,
                                 child_script=SCRIPT_CHILD)
    parent_script = scripts.dirpath().join('parent_script.py')

    result = testdir.runpytest('-v',
                               '--cov=%s' % scripts.dirpath(),
                               '--cov-report=term-missing',
                               parent_script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'child_script * %s *' % CHILD_SCRIPT_RESULT,
        'parent_script * %s *' % PARENT_SCRIPT_RESULT,
        ])
    assert result.ret == 0


def test_dist_subprocess_collocated(testdir):
    scripts = testdir.makepyfile(parent_script=SCRIPT_PARENT,
                                 child_script=SCRIPT_CHILD)
    parent_script = scripts.dirpath().join('parent_script.py')

    result = testdir.runpytest('-v',
                               '--cov=%s' % scripts.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=2*popen',
                               parent_script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'child_script * %s *' % CHILD_SCRIPT_RESULT,
        'parent_script * %s *' % PARENT_SCRIPT_RESULT,
        ])
    assert result.ret == 0


def test_dist_subprocess_not_collocated(testdir, tmpdir):
    scripts = testdir.makepyfile(parent_script=SCRIPT_PARENT,
                                 child_script=SCRIPT_CHILD)
    parent_script = scripts.dirpath().join('parent_script.py')
    child_script = scripts.dirpath().join('child_script.py')

    dir1 = tmpdir.mkdir('dir1')
    dir2 = tmpdir.mkdir('dir2')

    result = testdir.runpytest('-v',
                               '--cov=%s' % scripts.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=popen//chdir=%s' % dir1,
                               '--tx=popen//chdir=%s' % dir2,
                               '--rsyncdir=%s' % child_script,
                               '--rsyncdir=%s' % parent_script,
                               parent_script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'child_script * %s *' % CHILD_SCRIPT_RESULT,
        'parent_script * %s *' % PARENT_SCRIPT_RESULT,
        ])
    assert result.ret == 0


def test_empty_report(testdir):
    script = testdir.makepyfile(SCRIPT)

    result = testdir.runpytest('-v',
                               '--cov=non_existent_module',
                               '--cov-report=term-missing',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        '*10 passed*'
        ])
    assert result.ret == 0
    matching_lines = [line for line in result.outlines if '%' in line]
    assert not matching_lines


def test_dist_missing_data(testdir):
    venv_path = os.path.join(str(testdir.tmpdir), 'venv')
    virtualenv.create_environment(venv_path)
    if sys.platform == 'win32':
        exe = os.path.join(venv_path, 'Scripts', 'python.exe')
    else:
        exe = os.path.join(venv_path, 'bin', 'python')
    script = testdir.makepyfile(SCRIPT)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=popen//python=%s' % exe,
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: failed slaves -*'
        ])
    assert result.ret == 0


def test_funcarg(testdir):
    script = testdir.makepyfile(SCRIPT_FUNCARG)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_funcarg * 3 * 100%*',
        '*1 passed*'
        ])
    assert result.ret == 0


def test_funcarg_not_active(testdir):
    script = testdir.makepyfile(SCRIPT_FUNCARG_NOT_ACTIVE)

    result = testdir.runpytest('-v',
                               script)

    result.stdout.fnmatch_lines([
        '*1 passed*'
        ])
    assert result.ret == 0


def test_multiprocessing_subprocess(testdir):
    py.test.importorskip('multiprocessing.util')

    script = testdir.makepyfile(MULTIPROCESSING_SCRIPT)

    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)

    result.stdout.fnmatch_lines([
        '*- coverage: platform *, python * -*',
        'test_multiprocessing_subprocess * 8 * 100%*',
        '*1 passed*'
        ])
    assert result.ret == 0


MODULE = '''
def func():
    return 1

'''

CONFTEST = '''

import mod
mod.func()

'''

BASIC_TEST = '''

def test_basic():
    assert True

'''

CONF_RESULT = 'mod * 2 * 100% *'


def test_cover_conftest(testdir):
    testdir.makepyfile(mod=MODULE)
    testdir.makeconftest(CONFTEST)
    script = testdir.makepyfile(BASIC_TEST)
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)
    assert result.ret == 0
    result.stdout.fnmatch_lines([CONF_RESULT])


def test_cover_conftest_dist(testdir):
    testdir.makepyfile(mod=MODULE)
    testdir.makeconftest(CONFTEST)
    script = testdir.makepyfile(BASIC_TEST)
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '--dist=load',
                               '--tx=2*popen',
                               script)
    assert result.ret == 0
    result.stdout.fnmatch_lines([CONF_RESULT])


COVERAGERC = '''
[report]
# Regexes for lines to exclude from consideration
exclude_lines =
    raise NotImplementedError

'''

EXCLUDED_TEST = '''

def func():
    raise NotImplementedError

def test_basic():
    assert True

'''

EXCLUDED_RESULT = '3 * 100% *'


def test_coveragerc(testdir):
    testdir.makefile('', coveragerc=COVERAGERC)
    script = testdir.makepyfile(EXCLUDED_TEST)
    result = testdir.runpytest('-v',
                               '--cov-config=coveragerc',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)
    assert result.ret == 0
    result.stdout.fnmatch_lines(['test_coveragerc * %s' % EXCLUDED_RESULT])


def test_coveragerc_dist(testdir):
    testdir.makefile('', coveragerc=COVERAGERC)
    script = testdir.makepyfile(EXCLUDED_TEST)
    result = testdir.runpytest('-v',
                               '--cov-config=coveragerc',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               '-n', '2',
                               script)
    assert result.ret == 0
    result.stdout.fnmatch_lines(
        ['test_coveragerc_dist * %s' % EXCLUDED_RESULT])


CLEAR_ENVIRON_TEST = '''

import os

def test_basic():
    os.environ.clear()

'''


def test_clear_environ(testdir):
    script = testdir.makepyfile(CLEAR_ENVIRON_TEST)
    result = testdir.runpytest('-v',
                               '--cov=%s' % script.dirpath(),
                               '--cov-report=term-missing',
                               script)
    assert result.ret == 0
