import msvcrt
import os
import shutil
from pathlib import Path

# =====================================================
# 사용자 설정
# =====================================================
WW_PATH = Path(r"D:\Wuthering Waves\Wuthering Waves Game")
ZZZ_PATH = Path(r"C:\Program Files\HoYoPlay\games\ZenlessZoneZero Game")
STEAM_PATH = Path(r"E:\Program Files\Steam")


# =====================================================
# 유틸리티
# =====================================================
def clear_cache(folder: Path, name: str) -> None:
    if not folder.exists():
        print(f"[SKIP] {name} not found")
        return
    print(f"Clearing {name}...")
    try:
        shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)
        print(f"[OK] {name}")
    except Exception:
        print(f"[WARN] Some files locked. Failed to fully remove {name}")


def delete_file(file_path: Path, name: str) -> None:
    if not file_path.exists():
        print(f"[SKIP] {name} not found")
        return
    print(f"Deleting {name}...")
    try:
        file_path.unlink()
        if file_path.exists():
            print(f"[FAIL] {name}")
        else:
            print(f"[OK] {name}")
    except Exception:
        print(f"[FAIL] {name}")


# =====================================================
# 메인
# =====================================================
def main() -> None:
    localappdata = Path(os.environ["LOCALAPPDATA"])
    appdata = Path(os.environ["APPDATA"])
    userprofile = Path(os.environ["USERPROFILE"])
    programdata = Path(os.environ["ProgramData"])
    windir = Path(os.environ["WINDIR"])

    print("NOTE:")
    print("Some system caches may require Administrator privileges.")
    print("If some entries show [WARN], try running as Administrator.")
    print()
    print("=====================================================")
    print("       GPU Shader Cache Cleanup Utility")
    print("=====================================================")
    print()
    print("Recommended usage:")
    print("Run before/after GPU driver updates or to fix game stutters.")
    print()
    print("Press any key to start cleanup...")

    msvcrt.getch()

    print()
    print("==========================================")
    print("       Clearing GPU Shader Caches")
    print("==========================================")
    print()

    caches = [
        (localappdata / "D3DSCache", "Windows DirectX Shader Cache"),
        (localappdata / "Temp" / "DXCache", "DX12 Pipeline Cache"),
        (localappdata / "Microsoft" / "DirectX Shader Cache", "Windows DirectX Alt Cache"),
        (localappdata / "Temp" / "D3DCache", "Direct3D Pipeline Cache"),
        (localappdata / "Temp" / "NVIDIA Corporation" / "NV_Cache", "NVIDIA Temp Pipeline Cache"),
        (localappdata / "AMD" / "DXCache", "AMD DX Cache"),
        (localappdata / "AMD" / "GLCache", "AMD OpenGL Cache"),
        (localappdata / "AMD" / "VkCache", "AMD Vulkan Cache"),
        (localappdata / "AMD" / "DxcCache", "AMD DXC Cache"),
        (userprofile / "AppData" / "LocalLow" / "AMD" / "DxCache", "AMD LocalLow DX Cache"),
        (localappdata / "NVIDIA" / "DXCache", "NVIDIA DX Cache"),
        (localappdata / "NVIDIA" / "GLCache", "NVIDIA OpenGL Cache"),
        (localappdata / "NVIDIA" / "VkCache", "NVIDIA Vulkan Cache"),
        (appdata / "NVIDIA" / "ComputeCache", "NVIDIA Compute Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "DXCache", "NVIDIA PerDriver DX Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "GLCache", "NVIDIA PerDriver GL Cache"),
        (localappdata / "NVIDIA" / "PerDriverVersion" / "VkCache", "NVIDIA PerDriver Vulkan Cache"),
        (programdata / "NVIDIA Corporation" / "NV_Cache", "NVIDIA System NV Cache"),
        (userprofile / "AppData" / "LocalLow" / "NVIDIA" / "PerDriverVersion" / "DXCache", "NVIDIA LocalLow DX Cache"),
        (localappdata / "Intel" / "ShaderCache", "Intel Shader Cache"),
        (localappdata / "Intel" / "DXCache", "Intel DX Cache"),
        (localappdata / "Vulkan", "Vulkan Runtime Cache"),
        (localappdata / "cache" / "vulkan", "Generic Vulkan Cache"),
        (localappdata / "D3D12", "D3D12 Runtime Cache"),
        (windir / "Temp" / "DXCache", "Windows Temp DX Cache"),
        (STEAM_PATH / "steamapps" / "shadercache", "Steam Global Shader Cache"),
        (WW_PATH / "Client" / "Saved" / "PSO", "Wuthering Waves PSO Cache"),
        (WW_PATH / "Client" / "Saved" / "PSOReport", "Wuthering Waves PSO Report Cache"),
    ]

    for folder, name in caches:
        clear_cache(folder, name)

    # =====================================================
    # Zenless Zone Zero
    # =====================================================
    zzz_localstorage = ZZZ_PATH / "ZenlessZoneZero_Data" / "Persistent" / "LocalStorage"
    if zzz_localstorage.exists():
        print("Cleaning Zenless Zone Zero USD Cache...")
        for file in zzz_localstorage.glob("USD_*.bin"):
            try:
                file.unlink()
            except Exception:
                pass
        print("[OK] Zenless Zone Zero USD Cache")
    else:
        print("[SKIP] Zenless Zone Zero LocalStorage not found")

    # =====================================================
    # Endfield
    # =====================================================
    endfield_cache = userprofile / "AppData" / "LocalLow" / "Gryphline" / "Endfield" / "vulkan_pso_cache.bin"
    delete_file(endfield_cache, "Endfield Vulkan PSO Cache")

    print()
    print("==========================================")
    print("Cleanup complete.")
    print("==========================================")
    print()

    print("Press any key to proceed...")
    msvcrt.getch()


if __name__ == "__main__":
    main()
