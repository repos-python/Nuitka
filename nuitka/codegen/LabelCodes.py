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
""" C labels, small helpers.

Much things are handled with "goto" statements in the generated code, error
exits, finally blocks, etc. this provides just the means to emit a label or
the goto statement itself.
"""

def getGotoCode(label, emit):
    assert label is not None

    emit(
        "goto %s;" % label
    )

def getLabelCode(label, emit):
    assert label is not None

    emit(
        "%s:;" % label
    )
