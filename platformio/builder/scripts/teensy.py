# Copyright (C) Ivan Kravets <me@ikravets.com>
# See LICENSE for details.

"""
    Builder for Teensy boards
"""

import time
from os.path import isfile, join
from random import randint

from SCons.Script import (COMMAND_LINE_TARGETS, AlwaysBuild, Builder, Default,
                          DefaultEnvironment)

env = DefaultEnvironment()

if env.get("BOARD_OPTIONS", {}).get("build", {}).get("core") == "teensy":
    env.Replace(
        AR="avr-ar",
        AS="avr-gcc",
        CC="avr-gcc",
        CXX="avr-g++",
        OBJCOPY="avr-objcopy",
        RANLIB="avr-ranlib",

        ARFLAGS=["rcs"],

        CXXFLAGS=[
            "-std=c++0x"
        ],

        CPPFLAGS=[
            "-mmcu=$BOARD_MCU"
        ],

        CPPDEFINES=[
            "SERIALNUM=-%d" % randint(1000000000, 2000000000)
        ],

        LINKFLAGS=[
            "-mmcu=$BOARD_MCU"
        ]
    )

elif env.get("BOARD_OPTIONS", {}).get("build", {}).get("core") == "teensy3":
    env.Replace(
        AR="arm-none-eabi-ar",
        AS="arm-none-eabi-gcc",
        CC="arm-none-eabi-gcc",
        CXX="arm-none-eabi-g++",
        OBJCOPY="arm-none-eabi-objcopy",
        RANLIB="arm-none-eabi-ranlib",

        ARFLAGS=["rcs"],

        ASFLAGS=[
            "-mcpu=cortex-m4",
            "-mthumb",
            # "-nostdlib"
        ],

        CXXFLAGS=[
            "-std=gnu++0x",
            "-fno-rtti",
        ],

        CPPFLAGS=[
            "-mcpu=cortex-m4",
            "-mthumb",
            "-ffunction-sections",  # place each function in its own section
            "-fdata-sections",
            # "-nostdlib"
        ],

        CPPDEFINES=[
            "TIME_T=%d" % time.time()
        ],

        LINKFLAGS=[
            "-mcpu=cortex-m4",
            "-mthumb",
            "-Wl,--gc-sections",
            # "-nostartfiles",
            # "-nostdlib",
        ]
    )

env.Append(
    BUILDERS=dict(
        ElfToHex=Builder(
            action=" ".join([
                "$OBJCOPY",
                "-O",
                "ihex",
                "-R",
                ".eeprom",
                "$SOURCES",
                "$TARGET"]),
            suffix=".hex"
        )
    ),

    ASFLAGS=[
        "-c",
        "-g",  # include debugging info (so errors include line numbers)
        "-x", "assembler-with-cpp",
        "-Wall"
    ],

    CPPFLAGS=[
        "-g",   # include debugging info (so errors include line numbers)
        "-Os",  # optimize for size
        "-fdata-sections",
        "-ffunction-sections",  # place each function in its own section
        "-Wall",
        "-MMD"  # output dependancy info
    ],

    CPPDEFINES=[
        "F_CPU=$BOARD_F_CPU",
        "USB_PID=null",
        "USB_VID=null",
        "USB_SERIAL",
        "LAYOUT_US_ENGLISH"
    ],

    CXXFLAGS=[
        "-felide-constructors",
        "-fno-exceptions"
    ],

    LINKFLAGS=[
        "-Os"
    ]
)

if isfile(env.subst(join(
        "$PIOPACKAGES_DIR", "tool-teensy", "teensy_loader_cli"))):
    env.Append(
        UPLOADER=join("$PIOPACKAGES_DIR", "tool-teensy", "teensy_loader_cli"),
        UPLOADERFLAGS=[
            "-mmcu=$BOARD_MCU",
            "-w",  # wait for device to apear
            "-r",  # hard reboot if device not online
            "-v"   # verbose output
        ],
        UPLOADHEXCMD='"$UPLOADER" $UPLOADERFLAGS $SOURCES'
    )
else:
    env.Append(
        UPLOADER=join(
            "$PIOPACKAGES_DIR", "tool-teensy", "teensy_post_compile"),
        UPLOADERFLAGS=[
            "-file=firmware",
            '-path="$BUILD_DIR"',
            '-tools="%s"' % join("$PIOPACKAGES_DIR", "tool-teensy")
        ],
        UPLOADHEXCMD='"$UPLOADER" $UPLOADERFLAGS'
    )

CORELIBS = env.ProcessGeneral()

#
# Target: Build executable and linkable firmware
#

target_elf = env.BuildFirmware(CORELIBS + ["m"])

#
# Target: Build the .hex file
#

if "uploadlazy" in COMMAND_LINE_TARGETS:
    target_hex = join("$BUILD_DIR", "firmware.hex")
else:
    target_hex = env.ElfToHex(join("$BUILD_DIR", "firmware"), target_elf)

#
# Target: Upload by default .hex file
#

upload = env.Alias(["upload", "uploadlazy"], target_hex, ("$UPLOADHEXCMD"))
AlwaysBuild(upload)

#
# Target: Define targets
#

Default(target_hex)
