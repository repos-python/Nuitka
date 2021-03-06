#     Copyright 2014, Kay Hayen, mailto:kay.hayen@gmail.com
#
#     Part of "Nuitka", an optimizing Python compiler that is compatible and
#     integrates with CPython, but also works on its own.
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
#
""" Common test infrastructure functions. To be used by test runners. """

from __future__ import print_function

import os, sys, subprocess, tempfile, atexit, shutil, re

# Make sure we flush after every print, the "-u" option does more than that
# and this is easy enough.
def my_print(*args, **kwargs):
    print(*args, **kwargs)

    sys.stdout.flush()


def check_output(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(
        stdout = subprocess.PIPE,
        *popenargs,
        **kwargs
    )
    output, _unused_err = process.communicate()
    retcode = process.poll()

    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd, output = output)

    return output

def check_result(*popenargs, **kwargs):
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(
        stdout = subprocess.PIPE,
        *popenargs,
        **kwargs
    )
    _unused_output, _unused_err = process.communicate()
    retcode = process.poll()

    if retcode:
        return False
    else:
        return True


def setup(needs_io_encoding = False, silent = False):
    # Go its own directory, to have it easy with path knowledge.
    os.chdir(
        os.path.dirname(
            os.path.abspath(sys.modules[ "__main__" ].__file__)
        )
    )

    if "PYTHON" not in os.environ:
        os.environ["PYTHON"] = sys.executable

    # Allow providing 33, 27, and expand that to python2.7
    if len(os.environ["PYTHON"]) == 2 and \
       os.environ["PYTHON"].isdigit() and \
       os.name != "nt":

        os.environ["PYTHON"] = "python%s.%s" % (
            os.environ["PYTHON"][0],
            os.environ["PYTHON"][1]
        )

    if needs_io_encoding and "PYTHONIOENCODING" not in os.environ:
        os.environ["PYTHONIOENCODING"] = "utf-8"

    version_output = check_output(
        (
            os.environ["PYTHON"],
            "-c",
            """\
import sys, os;\
print(".".join(str(s) for s in list(sys.version_info)[:3]));\
print(("x86_64" if "AMD64" in sys.version else "x86") if os.name=="nt" else os.uname()[4]);\
""",
        ),
        stderr = subprocess.STDOUT
    )

    global python_version, python_arch
    python_version = version_output.split(b"\n")[0].strip()
    python_arch = version_output.split(b"\n")[1].strip()

    if sys.version.startswith("3"):
        python_arch = python_arch.decode()
        python_version = python_version.decode()

    os.environ["PYTHON_VERSION"] = python_version

    if not silent:
        my_print("Using concrete python", python_version, "on", python_arch)

    assert type(python_version) is str
    assert type(python_arch) is str

    return python_version


tmp_dir = None

def getTempDir():
    # Create a temporary directory to work in, automatically remove it in case
    # it is empty in the end.
    global tmp_dir

    if tmp_dir is None:
        tmp_dir = tempfile.mkdtemp(
            prefix = os.path.basename(
                os.path.dirname(
                    os.path.abspath(sys.modules[ "__main__" ].__file__)
                )
            ) + "-",
            dir    = tempfile.gettempdir() if
                         not os.path.exists("/var/tmp") else
                    "/var/tmp"
        )

        def removeTempDir():
            try:
                shutil.rmtree(tmp_dir)
            except OSError:
                pass

        atexit.register(removeTempDir)

    return tmp_dir


def convertUsing2to3(path):
    command = [
        os.environ["PYTHON"],
        "-m",
        "py_compile",
        path
    ]

    with open(os.devnull, "w") as stderr:
        if check_result(command, stderr = stderr):
            return path, False

    filename = os.path.basename(path)

    new_path = os.path.join(getTempDir(), filename)
    shutil.copy(path, new_path)

    # On Windows, we cannot rely on 2to3 to be in the path.
    if os.name == "nt":
        command = [
            sys.executable,
            os.path.join(
                os.path.dirname(sys.executable),
                "Tools/Scripts/2to3.py"
            )
        ]
    else:
        command = [
            "2to3"
        ]

    command += [
        "-w",
        "-n",
        "--no-diffs",
        new_path
    ]

    with open(os.devnull, "w") as devnull:
        check_output(
            command,
            stderr = devnull
        )

    return new_path, True


def decideFilenameVersionSkip(filename):
    assert type(filename) is str
    assert type(python_version) is str

    # Skip runner scripts by default.
    if filename.startswith("run_"):
        return False

    # Skip tests that require Python 2.7 at least.
    if filename.endswith("27.py") and python_version.startswith("2.6"):
        return False

    if filename.endswith("_2.py") and python_version.startswith("3"):
        return False

    # Skip tests that require Python 3.2 at least.
    if filename.endswith("32.py") and python_version < "3.2":
        return False

    # Skip tests that require Python 3.3 at least.
    if filename.endswith("33.py") and python_version < "3.3":
        return False

    # Skip tests that require Python 3.4 at least.
    if filename.endswith("34.py") and python_version < "3.4":
        return False

    return True


def compareWithCPython(path, extra_flags, search_mode, needs_2to3):
    # Apply 2to3 conversion if necessary.
    if needs_2to3:
        path, converted = convertUsing2to3(path)
    else:
        converted = False

    command = [
        sys.executable,
        os.path.join("..", "..", "bin", "compare_with_cpython"),
        path,
        "silent"
    ]
    command += extra_flags

    try:
        result = subprocess.call(
            command
        )
    except KeyboardInterrupt:
        result = 2

    if result != 0 and result != 2 and search_mode:
        my_print("Error exit!", result)
        sys.exit(result)

    if converted:
        os.unlink(path)

    if result == 2:
        sys.stderr.write("Interrupted, with CTRL-C\n")
        sys.exit(2)


def hasDebugPython():
    global python_version

    # On Debian systems, these work.
    debug_python = os.path.join("/usr/bin/", os.environ["PYTHON"] + "-dbg")
    if os.path.exists(debug_python):
        return True

    # For other Python, if it's the one also executing the runner, which is
    # very probably the case, we check that. We don't check the provided
    # binary here, this could be done as well.
    if sys.executable == os.environ["PYTHON"] and \
       hasattr(sys, "gettotalrefcount"):
        return True

    # Otherwise no.
    return False

def getArchitecture():
    if os.name == "nt":
        if "AMD64" in sys.version:
            return "x86_64"
        else:
            return "x86"
    else:
        return os.uname()[4]

def getDependsExePath():
    if "APPDATA" not in os.environ:
        sys.exit("Error, standalone mode cannot find 'APPDATA' environment.")

    nuitka_app_dir = os.path.join(os.environ["APPDATA"],"nuitka")

    depends_dir = os.path.join(
        nuitka_app_dir,
        python_arch,
    )
    depends_exe = os.path.join(
        depends_dir,
        "depends.exe"
    )

    assert os.path.exists(depends_exe), depends_exe

    return depends_exe


def getRuntimeTraceOfLoadedFiles(path,trace_error=True):
    """ Returns the files loaded when executing a binary. """

    result = []

    if os.name == "posix":
        if sys.platform == "darwin":
            args = (
                "sudo",
                "dtruss",
                "-f",
                "-t",
                "open",
                path
            )
        else:
            args = (
                "strace",
                "-e", "file",
                "-s4096", # Some paths are truncated otherwise.
                path
            )

        process = subprocess.Popen(
            args   = args,
            stdout = subprocess.PIPE,
            stderr = subprocess.PIPE
        )

        stdout_strace, stderr_strace = process.communicate()

        open(path+".strace","wb").write(stderr_strace)

        for line in stderr_strace.split(b"\n"):
            if process.returncode != 0 and trace_error:
                my_print(line)

            if not line:
                continue

            # Don't consider files not found. The "site" module checks lots
            # of things.
            if b"ENOENT" in line:
                continue

            if line.startswith(b"stat(") and b"S_IFDIR" in line:
                continue

            # Allow stats on the python binary, and stuff pointing to the
            # standard library, just not uses of it. It will search there
            # for stuff.
            if line.startswith(b"lstat(") or \
               line.startswith(b"stat(") or \
               line.startswith(b"readlink("):
                filename = line[line.find(b"(")+2:line.find(b", ")-1]

                if filename in (b"/usr", b"/usr/bin"):
                    continue

                if filename == b"/usr/bin/python" + python_version[:3].encode("utf8"):
                    continue

                if filename in (b"/usr/bin/python", b"/usr/bin/python2",
                                b"/usr/bin/python3"):
                    continue

            result.extend(
                os.path.abspath(match)
                for match in
                re.findall(b'"(.*?)(?:\\\\0)?"', line)
            )

        if sys.version.startswith("3"):
            result = [s.decode("utf-8") for s in result]
    elif os.name == "nt":
        subprocess.call(
            (
                getDependsExePath(),
                "-c",
                "-ot%s" % path + ".depends",
                "-f1",
                "-pa1",
                "-ps1",
                "-pp0",
                "-pl1",
                path
            )
        )

        inside = False
        for line in open(path + ".depends"):
            if "| Module Dependency Tree |" in line:
                inside = True
                continue

            if not inside:
                continue

            if "| Module List |" in line:
                break

            if "]" not in line:
                continue

            # Skip missing DLLs, apparently not needed anyway.
            if "?" in line[:line.find("]")]:
                continue

            dll_filename = line[line.find("]")+2:-1]
            assert os.path.isfile(dll_filename), dll_filename

            # The executable itself is of course exempted.
            if os.path.normcase(dll_filename) == \
                os.path.normcase(os.path.abspath(path)):
                continue

            dll_filename = os.path.normcase(dll_filename)

            result.append(dll_filename)

        os.unlink(path + ".depends")

    result = list(sorted(set(result)))

    return result

def hasModule(module_name):
    result = subprocess.call(
        (
            os.environ["PYTHON"],
            "-c"
            "import %s" % module_name
        ),
        stdout = open(os.devnull,"w"),
        stderr = subprocess.STDOUT
    )

    return result == 0

m1 = {}
m2 = {}

def snapObjRefCntMap(before):
    import gc

    if before:
        global m1
        m = m1
    else:
        global m2
        m = m2

    for x in gc.get_objects():
        if x is m1:
            continue

        if x is m2:
            continue

        m[ str(x) ] = sys.getrefcount(x)


def checkReferenceCount(checked_function, max_rounds = 10):
    assert sys.exc_info() == (None, None, None), sys.exc_info()

    print(checked_function.__name__ + ": ", end = "")
    sys.stdout.flush()

    ref_count1 = 17
    ref_count2 = 17

    explain = False

    import gc

    assert max_rounds > 0
    for count in range(max_rounds):
        gc.collect()
        ref_count1 = sys.gettotalrefcount()

        if explain and count == max_rounds - 1:
            snapObjRefCntMap(True)

        checked_function()

        # Not allowed, but happens when bugs occur.
        assert sys.exc_info() == (None, None, None), sys.exc_info()

        gc.collect()

        if explain and count == max_rounds - 1:
            snapObjRefCntMap(False)

        ref_count2 = sys.gettotalrefcount()

        if ref_count1 == ref_count2:
            result = True
            print("PASSED")
            break

        # print count, ref_count1, ref_count2
    else:
        result = False
        print("FAILED", ref_count1, ref_count2, "leaked", ref_count2 - ref_count1)

        if explain:
            assert m1
            assert m2

            for key in m1.keys():
                if key not in m2:
                    print("*" * 80)
                    print(key)
                elif m1[key] != m2[key]:
                    print("*" * 80)
                    print(key)
                else:
                    pass
                    # print m1[key]

    assert sys.exc_info() == (None, None, None), sys.exc_info()

    gc.collect()
    sys.stdout.flush()

    return result


def executeReferenceChecked(prefix, names, tests_skipped, tests_stderr):
    import gc
    gc.disable()

    extract_number = lambda name: int(name.replace(prefix, ""))

    # Find the function names.
    matching_names = tuple(
        name
        for name in names
        if name.startswith(prefix) and name[-1].isdigit()
    )

    old_stderr = sys.stderr

    # Everything passed
    result = True

    for name in sorted(matching_names, key = extract_number):
        number = extract_number(name)

        # print(tests_skipped)
        if number in tests_skipped:
            my_print(name + ": SKIPPED (%s)" % tests_skipped[number])
            continue

        # Avoid unraisable output.
        try:
            if number in tests_stderr:
                sys.stderr = open(os.devnull, "wb")
        except Exception: # Windows
            if not checkReferenceCount(names[name]):
                result = False
        else:
            if not checkReferenceCount(names[name]):
                result = False

            if number in tests_stderr:
                new_stderr = sys.stderr
                sys.stderr = old_stderr
                new_stderr.close()

    gc.enable()
    return result
