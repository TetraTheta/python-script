import msvcrt
import os
import shutil
from pathlib import Path

from library.console import ConsoleColor, format_box, format_status

# =====================================================
# 사용자 설정
# =====================================================
WW_PATH = Path(r"D:\Wuthering Waves\Wuthering Waves Game")
ZZZ_PATH = Path(r"C:\Program Files\HoYoPlay\games\ZenlessZoneZero Game")
STEAM_PATH = Path(r"E:\Program Files\Steam")


# =====================================================
# 유틸리티
# =====================================================
def get_error_label(error: OSError) -> str:
    winerror = getattr(error, "winerror", None)
    if winerror in {32, 33}:
        return "LOCK"
    if isinstance(error, PermissionError):
        return "PERM"
    if isinstance(error, FileNotFoundError):
        return "MISS"
    if isinstance(error, NotADirectoryError):
        return "TYPE"
    return "FAIL"


def print_failure(name: str, error: OSError) -> None:
    print(format_status(get_error_label(error), ConsoleColor.RED, name))


def clear_cache(folder: Path, name: str) -> None:
    if not folder.exists():
        print(format_status("SKIP", ConsoleColor.BLUE, f"{name} not found"))
        return

    print(format_status("INFO", ConsoleColor.GREEN, f"Clearing {name}..."))
    try:
        shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        print_failure(name, error)
        return

    print(format_status("REMOVE", ConsoleColor.YELLOW, name))


def delete_file(file_path: Path, name: str) -> None:
    if not file_path.exists():
        print(format_status("SKIP", ConsoleColor.BLUE, f"{name} not found"))
        return

    print(format_status("INFO", ConsoleColor.GREEN, f"Clearing {name}..."))
    try:
        file_path.unlink()
    except OSError as error:
        print_failure(name, error)
        return

    print(format_status("REMOVE", ConsoleColor.YELLOW, name))


def delete_matching_files(folder: Path, pattern: str, name: str) -> None:
    if not folder.exists():
        print(format_status("SKIP", ConsoleColor.BLUE, f"{name} not found"))
        return

    print(format_status("INFO", ConsoleColor.GREEN, f"Clearing {name}..."))
    try:
        for file in folder.glob(pattern):
            file.unlink()
    except OSError as error:
        print_failure(name, error)
        return

    print(format_status("REMOVE", ConsoleColor.YELLOW, name))


# =====================================================
# 메인
# =====================================================
def main() -> None:
    localappdata = Path(os.environ["LocalAppData"])
    appdata = Path(os.environ["AppData"])
    userprofile = Path(os.environ["UserProfile"])
    programdata = Path(os.environ["ProgramData"])
    windir = Path(os.environ["windir"])

    print(format_status("INFO", ConsoleColor.GREEN, "Some system caches may require Administrator privileges."))
    print(format_status("INFO", ConsoleColor.GREEN, "If some entries show PERM/LOCK, try running as Administrator."))
    print()
    print(format_box("GPU Shader Cache Cleanup Utility", ConsoleColor.BLUE))
    print()
    print(format_status("INFO", ConsoleColor.GREEN, "Run before/after GPU driver updates or to fix game stutters."))
    print()
    print("Press any key to start cleanup...")

    msvcrt.getch()

    print()
    print(format_box("Clearing GPU Shader Caches", ConsoleColor.BLUE))
    print()

    caches = [
        (localappdata / "AMD" / "DXCache", "AMD DX Cache"),
        (localappdata / "AMD" / "DxcCache", "AMD DXC Cache"),
        (userprofile / "AppData" / "LocalLow" / "AMD" / "DxCache", "AMD LocalLow DX Cache"),
        (localappdata / "AMD" / "GLCache", "AMD OpenGL Cache"),
        (localappdata / "AMD" / "VkCache", "AMD Vulkan Cache"),
        (localappdata / "D3D12", "D3D12 Runtime Cache"),
        (localappdata / "Temp" / "D3DCache", "Direct3D Pipeline Cache"),
        (localappdata / "Temp" / "DXCache", "DX12 Pipeline Cache"),
        (localappdata / "cache" / "vulkan", "Generic Vulkan Cache"),
        (localappdata / "Intel" / "DXCache", "Intel DX Cache"),
        (localappdata / "Intel" / "ShaderCache", "Intel Shader Cache"),
        (appdata / "NVIDIA" / "ComputeCache", "NVIDIA Compute Cache"),
        (localappdata / "NVIDIA" / "DXCache", "NVIDIA DX Cache"),
        (userprofile / "AppData" / "LocalLow" / "NVIDIA" / "PerDriverVersion" / "DXCache", "NVIDIA LocalLow DX Cache"),
        (localappdata / "NVIDIA" / "GLCache", "NVIDIA OpenGL Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "DXCache", "NVIDIA PerDriver DX Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "GLCache", "NVIDIA PerDriver GL Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "VkCache", "NVIDIA PerDriver Vulkan Cache"),
        (programdata / "NVIDIA Corporation" / "NV_Cache", "NVIDIA System NV Cache"),
        (localappdata / "Temp" / "NVIDIA Corporation" / "NV_Cache", "NVIDIA Temp Pipeline Cache"),
        (localappdata / "NVIDIA" / "VkCache", "NVIDIA Vulkan Cache"),
        (STEAM_PATH / "steamapps" / "shadercache", "Steam Global Shader Cache"),
        (localappdata / "Vulkan", "Vulkan Runtime Cache"),
        (localappdata / "Microsoft" / "DirectX Shader Cache", "Windows DirectX Alt Cache"),
        (localappdata / "D3DSCache", "Windows DirectX Shader Cache"),
        (windir / "Temp" / "DXCache", "Windows Temp DX Cache"),
        (WW_PATH / "Client" / "Saved" / "PSO", "Wuthering Waves PSO Cache"),
        (WW_PATH / "Client" / "Saved" / "PSOReport", "Wuthering Waves PSO Report Cache"),
    ]

    for folder, name in caches:
        clear_cache(folder, name)

    # =====================================================
    # Zenless Zone Zero
    # =====================================================
    zzz_localstorage = ZZZ_PATH / "ZenlessZoneZero_Data" / "Persistent" / "LocalStorage"
    delete_matching_files(zzz_localstorage, "USD_*.bin", "Zenless Zone Zero USD Cache")

    # =====================================================
    # Endfield
    # =====================================================
    endfield_cache = userprofile / "AppData" / "LocalLow" / "Gryphline" / "Endfield" / "vulkan_pso_cache.bin"
    delete_file(endfield_cache, "Endfield Vulkan PSO Cache")

    print()
    print(format_box("Cleanup complete.", ConsoleColor.BLUE))
    print()

    print("Press any key to proceed...")
    msvcrt.getch()


if __name__ == "__main__":
    main()
