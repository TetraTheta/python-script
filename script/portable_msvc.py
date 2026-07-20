#!/usr/bin/env python3
"""
MSVC 컴파일러를 Visual Studio Installer 없이 포터블로 저장한다 (작동 확인 필요)
필요 의존성: certifi
"""

import hashlib
import io
import json
import os
import re
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from argparse import ArgumentParser, Namespace
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import TypeVar
from urllib.request import Request

from library.text_file import write_text

T = TypeVar("T")


OUTPUT = Path("msvc")  # output folder (may be overridden by --location)
DOWNLOADS = Path("downloads")  # temporary download files

# NOTE: not all host & target architecture combinations are supported

DEFAULT_HOST = "x64"
ALL_HOSTS = ["x64", "x86", "arm64"]

DEFAULT_TARGET = "x64"
ALL_TARGETS = ["x64", "x86", "arm", "arm64"]

DEFAULT_VERSION = "latest"
ALL_VERSIONS = ["2019", "2022", "2026", "latest"]

MANIFEST_URLS = {
    "latest": ["https://aka.ms/vs/stable/channel", "https://aka.ms/vs/insiders/channel"],
    "2026": ["https://aka.ms/vs/18/stable/channel", "https://aka.ms/vs/18/insiders/channel"],
    "2022": ["https://aka.ms/vs/17/release/channel", "https://aka.ms/vs/17/pre/channel"],
    "2019": ["https://aka.ms/vs/16/release/channel", "https://aka.ms/vs/16/pre/channel"],
}

ssl_context: ssl.SSLContext | None = None


class PortableMsvcArgs(Namespace):
    accept_license: bool
    host: str
    insiders: bool
    location: str | None
    msvc_version: str | None
    sdk_version: str | None
    show_versions: bool
    target: str
    vs: str


def parse_args() -> PortableMsvcArgs:
    parser = ArgumentParser()
    parser.add_argument("--accept-license", action="store_true", help="Automatically accept license")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host architecture", choices=ALL_HOSTS)
    parser.add_argument("--insiders", "--preview", action="store_true", help="Use insiders/preview versions")
    parser.add_argument("--location", help="Base location to store MSVC (e.g. C:\\ or C:\\msvc)")
    parser.add_argument("--msvc-version", help="Get specific MSVC version")
    parser.add_argument("--sdk-version", help="Get specific Windows SDK version")
    parser.add_argument("--show-versions", action="store_true", help="Show available MSVC and Windows SDK versions")
    parser.add_argument(
        "--target", default=DEFAULT_TARGET, help=f"Target architectures, comma separated ({','.join(ALL_TARGETS)})"
    )
    parser.add_argument(
        "--vs", default=DEFAULT_VERSION, help="Visual Studio version to use for installation", choices=ALL_VERSIONS
    )
    return parser.parse_args(namespace=PortableMsvcArgs())


def download_bytes(url_or_req: str | Request) -> bytes:
    if isinstance(url_or_req, str):
        req = Request(url_or_req, headers={"User-Agent": "Mozilla/5.0"})
    else:
        req = url_or_req
    with urllib.request.urlopen(req, context=ssl_context) as res:
        return res.read()


total_download = 0


def download_with_cache(url: str, check: str | None, filename: str) -> bytes:
    fpath = DOWNLOADS / filename
    if fpath.exists():
        data = fpath.read_bytes()
        if check:
            if hashlib.sha256(data).hexdigest() == check.lower():
                print(f"\r{filename} ... OK")
                return data
        else:
            print(f"\r{filename} ... cached")
            return data

    global total_download
    with fpath.open("wb") as f:
        data = io.BytesIO()
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ssl_context) as res:
            total_hdr = res.headers["Content-Length"]
            total = int(total_hdr) if total_hdr and total_hdr.isdigit() else None
            size = 0
            while True:
                block = res.read(1 << 20)
                if not block:
                    break
                f.write(block)
                data.write(block)
                size += len(block)
                if total:
                    perc = size * 100 // total
                    print(f"\r{filename} ... {perc}%", end="")
                else:
                    print(f"\r{filename} ... {size // 20} MB", end="")
        print()
        data = data.getvalue()
        if check:
            digest = hashlib.sha256(data).hexdigest()
            if check.lower() != digest:
                sys.exit(f"Hash mismatch for {filename}")
        total_download += len(data)
        return data


# MSI 내부에서 필요한 CAB 파일 이름만 찾는 최소 스캐너
def iter_msi_cab_names(msi: bytes) -> Iterator[str]:
    index = 0
    while True:
        index = msi.find(b".cab", index + 4)
        if index < 0:
            return
        yield msi[index - 32 : index + 4].decode("ascii")


def find_first(items: Iterable[T], cond: Callable[[T], bool] = lambda item: True) -> T | None:
    return next((item for item in items if cond(item)), None)


def require_first(
    items: Iterable[T],
    cond: Callable[[T], bool] = lambda item: True,
    message: str = "Required item not found",
) -> T:
    item = find_first(items, cond)
    if item is None:
        sys.exit(message)
    return item


def download_cmake_windows() -> bool:
    try:
        html = download_bytes("https://cmake.org/download/").decode("utf-8", "ignore")
    except OSError as error:
        print("Warning: failed to fetch CMake download page:", error)
        return False

    m = re.search(r'href="([^"]*cmake-[^"]*-windows-x86_64.zip)"', html)
    if not m:
        print("Warning: could not find CMake Windows x64 ZIP link on cmake.org/download")
        return False
    zip_url = m.group(1)
    if zip_url.startswith("//"):
        zip_url = "https:" + zip_url
    elif zip_url.startswith("/"):
        zip_url = "https://cmake.org" + zip_url

    sha = None
    m2 = re.search(r'href="([^"]*cmake-[^"]*-SHA-256.txt)"', html)
    if m2:
        sha_url = m2.group(1)
        if sha_url.startswith("//"):
            sha_url = "https:" + sha_url
        elif sha_url.startswith("/"):
            sha_url = "https://cmake.org" + sha_url
        try:
            sha_text = download_bytes(sha_url).decode("utf-8", "ignore")
            zipname = zip_url.split("/")[-1]
            for line in sha_text.splitlines():
                if zipname in line:
                    mh = re.search(r"([a-fA-F0-9]{64})", line)
                    if mh:
                        sha = mh.group(1)
                        break
        except OSError:
            sha = None

    filename = zip_url.split("/")[-1]
    print(f"Downloading {filename} ...")
    try:
        data = download_with_cache(zip_url, sha, filename)
    except OSError as error:
        print("Warning: failed to download CMake:", error)
        return False

    with tempfile.TemporaryDirectory(dir=DOWNLOADS) as td:
        td = Path(td)
        zf = zipfile.ZipFile(io.BytesIO(data))
        zf.extractall(td)
        entries = list(td.iterdir())
        # zip 안에 단일 최상위 폴더만 있으면 그 내부 파일을 설치 위치로 올림
        if len(entries) == 1 and entries[0].is_dir():
            src = entries[0]
        else:
            src = td
        dest = OUTPUT / "CMake"
        dest.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            target = dest / item.name
            if item.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.move(str(item), str(target))
            else:
                shutil.move(str(item), str(target))
    print("CMake installed to", OUTPUT / "CMake")
    return True


def download_ninja_windows() -> bool:
    zip_url = "https://github.com/ninja-build/ninja/releases/latest/download/ninja-win.zip"
    filename = "ninja-win.zip"
    try:
        data = download_with_cache(zip_url, None, filename)
    except OSError as error:
        print("Warning: failed to download Ninja:", error)
        return False

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.lower().endswith("ninja.exe"):
                destdir = OUTPUT / "Ninja"
                destdir.mkdir(parents=True, exist_ok=True)
                out = destdir / "ninja.exe"
                out.write_bytes(zf.read(name))
                # Windows에서는 영향이 작지만 다른 환경에서도 실행 비트를 맞춤
                try:
                    st = os.stat(out)
                    os.chmod(out, st.st_mode | stat.S_IEXEC)
                except OSError:
                    pass
                print("Ninja installed to", out)
                return True

    print("Warning: ninja.exe not found inside ninja-win.zip")
    return False


def main() -> None:
    global DOWNLOADS, OUTPUT, ssl_context

    args = parse_args()
    if args.location:
        loc = Path(args.location)
        if loc.name.lower() == "msvc":
            OUTPUT = loc
            DOWNLOADS = loc.parent / "download"
        else:
            OUTPUT = loc / "msvc"
            DOWNLOADS = loc / "downloads"

    host = args.host
    targets = args.target.split(",")
    for target in targets:
        if target not in ALL_TARGETS:
            sys.exit(f"Unknown {target} target architecture!")

    # Visual Studio 채널 manifest를 내려받아 이후 패키지 선택의 기준으로 삼음

    URL = MANIFEST_URLS[args.vs][args.insiders]

    try:
        manifest = json.loads(download_bytes(URL))
    except urllib.error.URLError as err:
        if isinstance(err.args[0], ssl.SSLCertVerificationError):
            # See https://stackoverflow.com/a/52074591 for Windows certificate details.
            print("ERROR: ssl certificate verification error")
            try:
                import certifi  # pyright: ignore[reportMissingImports] - This must be installed by user
            except ModuleNotFoundError:
                print("ERROR: please install 'certifi' package to use Mozilla certificates")
                print(
                    "ERROR: or update your Windows certs. See: "
                    "https://woshub.com/updating-trusted-root-certificates-in-windows-10/#h2_3"
                )
                sys.exit()
            print("NOTE: retrying with certifi certificates")
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            manifest = json.loads(download_bytes(URL))
        else:
            raise

    # 제품별 세부 패키지 manifest를 내려받음

    ITEM_NAME = (
        "Microsoft.VisualStudio.Manifests.VisualStudioPreview"
        if args.insiders
        else "Microsoft.VisualStudio.Manifests.VisualStudio"
    )

    vs = require_first(
        manifest["channelItems"],
        lambda x: x["id"] == ITEM_NAME,
        "Visual Studio manifest item not found in channel manifest",
    )
    payload = vs["payloads"][0]["url"]

    vsmanifest = json.loads(download_bytes(payload))

    # 요청된 MSVC와 Windows SDK 버전을 manifest에서 결정

    packages = {}
    for p in vsmanifest["packages"]:
        packages.setdefault(p["id"].lower(), []).append(p)

    msvc = {}
    sdk = {}

    for pid, p in packages.items():
        if pid.startswith("Microsoft.VC.".lower()) and pid.endswith(".Tools.HostX64.TargetX64.base".lower()):
            pver = ".".join(pid.split(".")[2:4])
            if pver[0].isnumeric():
                msvc[pver] = pid
        elif pid.startswith("Microsoft.VisualStudio.Component.Windows10SDK.".lower()) or pid.startswith(
            "Microsoft.VisualStudio.Component.Windows11SDK.".lower()
        ):
            pver = pid.split(".")[-1]
            if pver.isnumeric():
                sdk[pver] = pid

    if args.show_versions:
        print("MSVC versions:", " ".join(sorted(msvc.keys())))
        print("Windows SDK versions:", " ".join(sorted(sdk.keys())))
        sys.exit(0)

    msvc_ver = args.msvc_version or max(sorted(msvc.keys()))
    sdk_ver = args.sdk_version or max(sorted(sdk.keys()))

    if msvc_ver in msvc:
        msvc_pid = msvc[msvc_ver]
        msvc_ver = ".".join(msvc_pid.split(".")[2:6])
    else:
        sys.exit(f"Unknown MSVC version: f{args.msvc_version}")

    if sdk_ver in sdk:
        sdk_pid = sdk[sdk_ver]
    else:
        sys.exit(f"Unknown Windows SDK version: f{args.sdk_version}")

    print(f"Downloading MSVC v{msvc_ver} and Windows SDK v{sdk_ver}")

    # 자동 동의 옵션이 없으면 라이선스 URL을 보여 주고 명시적 동의를 받음

    tools = require_first(
        manifest["channelItems"],
        lambda x: x["id"] == "Microsoft.VisualStudio.Product.BuildTools",
        "BuildTools product item not found in channel manifest",
    )
    resource = require_first(
        tools["localizedResources"],
        lambda x: x["language"] == "en-us",
        "en-us localized resource not found for BuildTools",
    )
    license = resource["license"]

    if not args.accept_license:
        accept = input(f"Do you accept Visual Studio license at {license} [Y/N] ? ")
        if not accept or accept[0].lower() != "y":
            sys.exit(0)

    OUTPUT.mkdir(exist_ok=True)
    DOWNLOADS.mkdir(exist_ok=True)

    # 선택된 target 아키텍처에 필요한 MSVC 패키지를 내려받고 압축을 풂

    msvc_packages = [
        "microsoft.visualcpp.dia.sdk",
        f"microsoft.vc.{msvc_ver}.crt.headers.base",
        f"microsoft.vc.{msvc_ver}.crt.source.base",
        f"microsoft.vc.{msvc_ver}.asan.headers.base",
        f"microsoft.vc.{msvc_ver}.pgo.headers.base",
        f"microsoft.vc.{msvc_ver}.atl.headers.base",
    ]

    for target in targets:
        msvc_packages += [
            f"microsoft.vc.{msvc_ver}.tools.host{host}.target{target}.base",
            f"microsoft.vc.{msvc_ver}.tools.host{host}.target{target}.res.base",
            f"microsoft.vc.{msvc_ver}.crt.{target}.desktop.base",
            f"microsoft.vc.{msvc_ver}.crt.{target}.store.base",
            f"microsoft.vc.{msvc_ver}.premium.tools.host{host}.target{target}.base",
            f"microsoft.vc.{msvc_ver}.pgo.{target}.base",
            f"microsoft.vc.{msvc_ver}.atl.{target}.base",
        ]
        if target in ["x86", "x64"]:
            msvc_packages += [f"microsoft.vc.{msvc_ver}.asan.{target}.base"]

        redist_suffix = ".onecore.desktop" if target == "arm" else ""
        redist_pkg = f"microsoft.vc.{msvc_ver}.crt.redist.{target}{redist_suffix}.base"
        if redist_pkg not in packages:
            redist_name = f"microsoft.visualcpp.crt.redist.{target}{redist_suffix}"
            redist = require_first(
                packages[redist_name],
                message=f"Redistributable package entry not found: {redist_name}",
            )
            redist_dep = require_first(
                redist["dependencies"],
                lambda dep: dep.endswith(".base"),
                message=f"Base dependency not found for package: {redist_name}",
            )
            redist_pkg = redist_dep.lower()
        msvc_packages += [redist_pkg]

    for pkg in sorted(msvc_packages):
        if pkg not in packages:
            print(f"\r{pkg} ... !!! MISSING !!!")
            continue
        p = require_first(
            packages[pkg],
            lambda package_item: package_item.get("language") in (None, "en-US"),
            message=f"Package payload metadata not found: {pkg}",
        )
        for payload in p["payloads"]:
            filename = payload["fileName"]
            download_with_cache(payload["url"], payload["sha256"], filename)
            with zipfile.ZipFile(DOWNLOADS / filename) as z:
                for name in z.namelist():
                    if name.startswith("Contents/"):
                        out = OUTPUT / Path(name).relative_to("Contents")
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(z.read(name))

    # Windows SDK MSI와 CAB 파일을 내려받아 관리 설치 방식으로 풂

    sdk_packages = [
        "Windows SDK for Windows Store Apps Tools-x86_en-us.msi",
        "Windows SDK for Windows Store Apps Headers-x86_en-us.msi",
        "Windows SDK for Windows Store Apps Headers OnecoreUap-x86_en-us.msi",
        "Windows SDK for Windows Store Apps Libs-x86_en-us.msi",
        "Universal CRT Headers Libraries and Sources-x86_en-us.msi",
    ]

    for target in ALL_TARGETS:
        sdk_packages += [
            f"Windows SDK Desktop Headers {target}-x86_en-us.msi",
            f"Windows SDK OnecoreUap Headers {target}-x86_en-us.msi",
        ]

    for target in targets:
        sdk_packages += [f"Windows SDK Desktop Libs {target}-x86_en-us.msi"]

    with tempfile.TemporaryDirectory(dir=DOWNLOADS) as d:
        dst = Path(d)

        sdk_pkg = packages[sdk_pid][0]
        sdk_dep = require_first(
            sdk_pkg["dependencies"],
            message=f"SDK dependency not found for package: {sdk_pid}",
        )
        sdk_pkg = packages[sdk_dep.lower()][0]

        msi = []
        cabs = []

        # MSI 파일을 먼저 받아 필요한 CAB 이름을 수집
        for pkg in sorted(sdk_packages):
            payload = find_first(sdk_pkg["payloads"], lambda p: p["fileName"] == f"Installers\\{pkg}")
            if payload is None:
                continue
            msi.append(DOWNLOADS / pkg)
            data = download_with_cache(payload["url"], payload["sha256"], pkg)
            cabs += list(iter_msi_cab_names(data))

        # MSI가 참조하는 CAB 파일을 이어서 내려받음
        for pkg in cabs:
            payload = require_first(
                sdk_pkg["payloads"],
                lambda p: p["fileName"] == f"Installers\\{pkg}",
                message=f"Installer payload not found for cab: {pkg}",
            )
            download_with_cache(payload["url"], payload["sha256"], pkg)

        print("Unpacking msi files...")

        # run msi installers
        for m in msi:
            subprocess.check_call(f'msiexec.exe /a "{m}" /quiet /qn TARGETDIR="{OUTPUT.resolve()}"')
            (OUTPUT / m.name).unlink()

    # Attempt the downloads (non-fatal; the script will continue if they fail)
    cmake_ok = download_cmake_windows()
    ninja_ok = download_ninja_windows()

    # 설치된 MSVC/SDK 버전 폴더를 찾아 후속 정리 경로에 사용

    msvcv = require_first(
        (OUTPUT / "VC/Tools/MSVC").glob("*"),
        message="Installed MSVC version directory not found",
    ).name
    sdkv = require_first(
        (OUTPUT / "Windows Kits/10/bin").glob("*"),
        message="Installed Windows SDK bin directory not found",
    ).name

    # Place debug CRT runtime files into MSVC bin folder.
    # NOTE: these are Target architecture, not Host architecture binaries

    redist = OUTPUT / "VC/Redist"

    if redist.exists():
        redistv = require_first(
            (redist / "MSVC").glob("*"),
            message="MSVC redist version directory not found",
        ).name
        src = redist / "MSVC" / redistv / "debug_nonredist"
        for target in targets:
            for f in (src / target).glob("**/*.dll"):
                dst = OUTPUT / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}" / target
                f.replace(dst / f.name)

        shutil.rmtree(redist)

    # Copy msdia140.dll file into MSVC bin folder.
    # NOTE: this is meant only for development and is always Host architecture.

    msdia140dll = {
        "x86": "msdia140.dll",
        "x64": "amd64/msdia140.dll",
        "arm": "arm/msdia140.dll",
        "arm64": "arm64/msdia140.dll",
    }

    dst = OUTPUT / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}"
    src = OUTPUT / "DIA%20SDK/bin" / msdia140dll[host]
    for target in targets:
        shutil.copyfile(src, dst / target / src.name)

    shutil.rmtree(OUTPUT / "DIA%20SDK")

    # 배포용 portable toolchain에 필요 없는 파일과 아키텍처를 정리

    shutil.rmtree(OUTPUT / "Common7", ignore_errors=True)
    shutil.rmtree(OUTPUT / "VC/Tools/MSVC" / msvcv / "Auxiliary")
    for target in targets:
        for f in ["store", "uwp", "enclave", "onecore"]:
            shutil.rmtree(OUTPUT / "VC/Tools/MSVC" / msvcv / "lib" / target / f, ignore_errors=True)
        shutil.rmtree(
            OUTPUT / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}" / target / "onecore",
            ignore_errors=True,
        )
    for f in ["Catalogs", "DesignTime", f"bin/{sdkv}/chpe", f"Lib/{sdkv}/ucrt_enclave"]:
        shutil.rmtree(OUTPUT / "Windows Kits/10" / f, ignore_errors=True)
    for arch in ["x86", "x64", "arm", "arm64"]:
        if arch not in targets:
            shutil.rmtree(OUTPUT / "Windows Kits/10/Lib" / sdkv / "ucrt" / arch, ignore_errors=True)
            shutil.rmtree(OUTPUT / "Windows Kits/10/Lib" / sdkv / "um" / arch, ignore_errors=True)
        if arch != host:
            shutil.rmtree(OUTPUT / "VC/Tools/MSVC" / msvcv / f"bin/Host{arch}", ignore_errors=True)
            shutil.rmtree(OUTPUT / "Windows Kits/10/bin" / sdkv / arch, ignore_errors=True)

    # executable that is collecting & sending telemetry every time cl/link runs
    for target in targets:
        (OUTPUT / "VC/Tools/MSVC" / msvcv / f"bin/Host{host}/{target}/vctip.exe").unlink(missing_ok=True)

    # extra files for nvcc
    build = OUTPUT / "VC/Auxiliary/Build"
    build.mkdir(parents=True, exist_ok=True)
    write_text(build / "vcvarsall.bat", "rem both bat files are here only for nvcc, do not call them manually")
    (build / "vcvars64.bat").touch()

    # target별 setup 배치 파일을 만들어 환경 변수를 한 번에 설정

    for target in targets:
        path_value = (
            rf"%~dp0VC\Tools\MSVC\{msvcv}\bin\Host{host}\{target};"
            rf"%~dp0Windows Kits\10\bin\{sdkv}\{host};"
            rf"%~dp0Windows Kits\10\bin\{sdkv}\{host}\ucrt;"
            r"%~dp0CMake\bin;%~dp0Ninja;%PATH%"
        )
        include_value = (
            rf"%~dp0VC\Tools\MSVC\{msvcv}\include;"
            rf"%~dp0Windows Kits\10\Include\{sdkv}\ucrt;"
            rf"%~dp0Windows Kits\10\Include\{sdkv}\shared;"
            rf"%~dp0Windows Kits\10\Include\{sdkv}\um;"
            rf"%~dp0Windows Kits\10\Include\{sdkv}\winrt;"
            rf"%~dp0Windows Kits\10\Include\{sdkv}\cppwinrt"
        )
        lib_value = (
            rf"%~dp0VC\Tools\MSVC\{msvcv}\lib\{target};"
            rf"%~dp0Windows Kits\10\Lib\{sdkv}\ucrt\{target};"
            rf"%~dp0Windows Kits\10\Lib\{sdkv}\um\{target}"
        )
        SETUP = rf"""@echo off

    set "VSCMD_ARG_HOST_ARCH={host}"
    set "VSCMD_ARG_TGT_ARCH={target}"

    set "VCToolsVersion={msvcv}"
    set "WindowsSDKVersion={sdkv}"

    set "WindowsSdkDir=%~dp0Windows Kits\10\"
    set "UniversalCRTSdkDir=%~dp0Windows Kits\10\"
    set "UCRTVersion={sdkv}"

    set "VCToolsInstallDir=%~dp0VC\Tools\MSVC\{msvcv}\"
    set "WindowsSdkBinPath=%~dp0Windows Kits\10\bin\"

    set "PATH={path_value}"
    set "INCLUDE={include_value}"
    set "LIB={lib_value}"
    """
        write_text(OUTPUT / f"setup_{target}.bat", SETUP)

    print(f"Total downloaded: {total_download >> 20} MB")
    print("Done!")

    if cmake_ok and ninja_ok:
        print("CMake and Ninja were downloaded and installed into the msvc tree.")
    else:
        print("CMake and/or Ninja were not fully installed. You can manually add them under the msvc directory:")
        print("  - <location>/msvc/CMake/bin (must contain 'share' next to 'bin')")
        print("  - <location>/msvc/Ninja/ninja.exe")


if __name__ == "__main__":
    main()
