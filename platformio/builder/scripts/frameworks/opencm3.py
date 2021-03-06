# Copyright (C) Ivan Kravets <me@ikravets.com>
# See LICENSE for details.

"""
    Build script for OpenCM3 Framework.
"""

import re
from os import listdir, sep, walk
from os.path import isfile, join, normpath

from SCons.Script import Import, Return

from platformio.util import exec_command

env = None
Import("env")
BOARD_BUILDOPTS = env.get("BOARD_OPTIONS", {}).get("build", {})


def find_ldscript(src_dir):
    ldscript = None
    matches = []
    for item in listdir(src_dir):
        _path = join(src_dir, item)
        if not isfile(_path) or not item.endswith(".ld"):
            continue
        matches.append(_path)

    if len(matches) == 1:
        ldscript = matches[0]
    elif isfile(join(src_dir, BOARD_BUILDOPTS['ldscript'])):
        ldscript = join(src_dir, BOARD_BUILDOPTS['ldscript'])

    assert isfile(ldscript)
    return ldscript


def generate_nvic_files():
    fw_dir = join(env.get("PIOHOME_DIR"), "packages", "framework-opencm3")

    for root, _, files in walk(join(fw_dir, "include", "libopencm3")):
        if "irq.json" not in files or isfile(join(root, "nvic.h")):
            continue

        exec_command(
            ["python", join("scripts", "irq2nvic_h"),
             join("." + root.replace(fw_dir, ""),
                  "irq.json").replace("\\", "/")],
            cwd=fw_dir
        )


def parse_makefile_data(makefile):
    data = {"includes": [], "objs": [], "vpath": ["./"]}

    with open(makefile) as f:
        content = f.read()

        # fetch "includes"
        re_include = re.compile(r"^include\s+([^\r\n]+)", re.M)
        for match in re_include.finditer(content):
            data['includes'].append(match.group(1))

        # fetch "vpath"s
        re_vpath = re.compile(r"^VPATH\s+\+?=\s+([^\r\n]+)", re.M)
        for match in re_vpath.finditer(content):
            data['vpath'] += match.group(1).split(":")

        # fetch obj files
        objs_match = re.search(
            r"^OBJS\s+\+?=\s+([^\.]+\.o\s*(?:\s+\\s+)?)+", content, re.M)
        assert objs_match
        data['objs'] = re.sub(
            r"(OBJS|[\+=\\\s]+)", "\n", objs_match.group(0)).split()
    return data


def get_source_files(src_dir):
    mkdata = parse_makefile_data(join(src_dir, "Makefile"))

    for include in mkdata['includes']:
        _mkdata = parse_makefile_data(normpath(join(src_dir, include)))
        for key, value in _mkdata.iteritems():
            for v in value:
                if v not in mkdata[key]:
                    mkdata[key].append(v)

    sources = []
    lib_root = env.subst(
        join(env.get("PIOHOME_DIR"), "packages", "framework-opencm3"))
    for obj_file in mkdata['objs']:
        src_file = obj_file[:-1] + "c"
        for search_path in mkdata['vpath']:
            src_path = normpath(join(src_dir, search_path, src_file))
            if isfile(src_path):
                sources.append(join("$BUILD_DIR", "FrameworkOpenCM3",
                                    src_path.replace(lib_root + sep, "")))
                break
    return sources


def merge_ld_scripts(main_ld_file):

    def _include_callback(match):
        included_ld_file = match.group(1)
        # search included ld file in lib directories
        for root, _, files in walk(join(
                env.get("PIOHOME_DIR"), "packages",
                "framework-opencm3", "lib")):

            if included_ld_file not in files:
                continue
            with open(join(root, included_ld_file)) as fp:
                return fp.read()

        return match.group(0)

    content = ""
    with open(main_ld_file) as f:
        content = f.read()

    incre = re.compile(r"^INCLUDE\s+\"?([^\.]+\.ld)\"?", re.M)
    with open(main_ld_file, "w") as f:
        f.write(incre.sub(_include_callback, content))

#
# Processing ...
#

if BOARD_BUILDOPTS.get("core") == "lm4f":
    env.Append(
        CPPDEFINES=["LM4F"]
    )

env.VariantDir(
    join("$BUILD_DIR", "FrameworkOpenCM3Variant"),
    join("$PIOPACKAGES_DIR", "framework-opencm3", "include")
)

env.Append(
    CPPPATH=[
        join("$BUILD_DIR", "FrameworkOpenCM3"),
        join("$BUILD_DIR", "FrameworkOpenCM3Variant")
    ]
)

root_dir = join(env.get("PIOHOME_DIR"), "packages", "framework-opencm3", "lib",
                BOARD_BUILDOPTS.get("core"))
if BOARD_BUILDOPTS.get("core") == "stm32":
    root_dir = join(root_dir, BOARD_BUILDOPTS.get("variant")[-2:])

ldscript_path = find_ldscript(root_dir)
merge_ld_scripts(ldscript_path)
generate_nvic_files()

# override ldscript by opencm3
assert "-T" in env['LINKFLAGS']
env['LINKFLAGS'][env['LINKFLAGS'].index("-T") + 1] = ldscript_path

libs = []
env.VariantDir(
    join("$BUILD_DIR", "FrameworkOpenCM3"),
    join(env.get("PIOHOME_DIR"), "packages", "framework-opencm3")
)
libs.append(env.Library(
    join("$BUILD_DIR", "FrameworkOpenCM3"),
    get_source_files(root_dir)
))

Return("env libs")
