import json
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.messagebox as msgbox
import tkinter.ttk as ttk
from pathlib import Path
from typing import List, TypedDict

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff")


class JobFile(TypedDict):
    operation: str
    game: str
    blur: List[List[int]]
    crop_height: int
    crop_pos: str
    save_at_parent: bool
    target: str | Path
    width_from: int
    width_to: int
    delete_job_file: bool


class ConvertScreenshotGUI:
    def __init__(self, job: JobFile, job_file_path: Path, verbose: bool = False):
        self.verbose = verbose
        self.had_error = False

        # get job file
        self.job = job
        self.job_file_path = job_file_path
        self.queue = queue.Queue()

        self.target_dir = Path(job["target"])
        self.temp_dir = self.target_dir / "cs-temp"
        self.converted_dir = self.target_dir.parent if job["save_at_parent"] else self.target_dir / "converted"

        # root UI
        self.root = tk.Tk()
        self.root.geometry("484x461")
        self.root.resizable(False, False)
        self.root.title("ConvertScreenshot")
        # self.root.bind("<Destroy>", self.on_close_window)

        # global style
        self.root.option_add("*TLabel.font", "{Segoe UI} 10")
        self.root.option_add("*Text.font", "{Consolas} 10")

        # 1st Text row
        self.labelTarget = ttk.Label(self.root, text=f"Target: {self.job['target']}")
        self.labelTarget.configure(justify="left")
        self.labelTarget.pack(fill="x", padx=8, pady=(8, 0), side="top")

        # 2nd Text row
        self.labelGame = ttk.Label(self.root, text=f"Game: {self.job['game']}")
        self.labelGame.configure(justify="left")
        self.labelGame.pack(fill="x", padx=8, pady=(8, 8), side="top")

        # 3rd Text row
        self.labelOperation = ttk.Label(self.root, text=f"Operation: {self.job['operation']}")
        self.labelOperation.configure(justify="left")
        self.labelOperation.pack(fill="x", padx=8, pady=(0, 8), side="top")

        # progress bar
        self.progress = ttk.Progressbar(self.root)
        self.prog = tk.IntVar(value=0)
        self.progress.configure(variable=self.prog)
        self.progress.pack(fill="x", padx=8, pady=(0, 8), side="top")

        # log
        self.textLog = tk.Text(self.root, wrap="word", state="disabled")
        self.textLog.pack(expand=True, fill="both", padx=8, pady=(0, 8), side="top")

        self.root.after(100, self.process_queue)
        # t = threading.Thread(target=self.run_job, daemon=True)
        t = threading.Thread(target=self.run_job)
        t.start()

    def check_dependencies(self) -> bool:
        binaries = {"ffmpeg": "ffmpeg", "cwebp": "cwebp", "get-image-dimension": "get-image-dimension"}
        results = []
        all_found = True

        for name, cmd in binaries.items():
            path = shutil.which(cmd)
            if path:
                results.append(f"✅ {name}: Found")
            else:
                results.append(f"❌ {name}: NOT FOUND")
                all_found = False

        if not all_found:
            msg = "Missing required dependencies:\n\n" + "\n".join(results)
            msg += "\n\nPlease install missing binaries and try again."
            msgbox.showerror("Dependency Error", msg)

        return all_found

    def center_window(self):
        if self.root.winfo_ismapped():
            min_w, min_h = self.root.wm_minsize()
            max_w, max_h = self.root.wm_maxsize()
            scr_w = self.root.winfo_screenwidth()
            scr_h = self.root.winfo_screenheight()
            final_w = min(scr_w, max_w, max(min_w, self.root.winfo_width(), self.root.winfo_reqwidth()))
            final_h = min(scr_h, max_h, max(min_h, self.root.winfo_height(), self.root.winfo_reqheight()))
            x = (scr_w // 2) - (final_w // 2)
            y = (scr_h // 2) - (final_h // 2)
            geometry = f"{final_w}x{final_h}+{x}+{y}"

            def set_geometry():
                self.root.geometry(geometry)

            self.root.after_idle(set_geometry)
        else:
            self.root.after(5, self.center_window)

    def run(self, center=False):
        if center:
            self.center_window()
        self.root.mainloop()

    def process_queue(self):
        try:
            while True:
                cmd, val = self.queue.get_nowait()
                if cmd == "LOG":
                    self.textLog.configure(state="normal")
                    self.textLog.insert("end", val + "\n")
                    self.textLog.configure(state="disabled")
                    self.textLog.see("end")
                elif cmd == "PROG":
                    self.prog.set(val)
                elif cmd == "PROG_MAX":
                    self.progress.configure(maximum=val)
                elif cmd == "FLASH":
                    self.flash_window()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    def flash_window(self):
        if sys.platform != "win32":
            return

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = self.root.winfo_id()

        FLASHW_ALL = 3
        FLASHW_TIMERNOFG = 12

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.UINT),
                ("hwnd", wintypes.HWND),
                ("dwFlags", wintypes.DWORD),
                ("uCount", wintypes.UINT),
                ("dwTimeout", wintypes.DWORD),
            ]

        flash = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 5, 0)
        user32.FlashWindowEx(ctypes.byref(flash))

    def log(self, msg: str, isverbose: bool = False):
        if not isverbose or self.verbose:
            self.queue.put(("LOG", msg))

    def update_prog(self, val, maximum=None):
        if maximum is not None:
            self.queue.put(("PROG_MAX", maximum))
        self.queue.put(("PROG", val))

    def run_job(self):
        try:
            self.prepare_dirs()
            self.process_images()
            self.log("----------------\nJob finished successfully.")
        except Exception as e:
            self.had_error = True
            self.log(f"----------------\nERROR: {e}")
        finally:
            self.cleanup()
            if self.had_error:
                self.queue.put(("FLASH", None))
            else:
                self.root.after(0, self.root.destroy)

    def prepare_dirs(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        if not self.converted_dir.exists():
            self.converted_dir.mkdir(parents=True, exist_ok=True)

    def process_images(self):
        files = [p for p in self.target_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS]
        if not files:
            self.log("No images found.")
            return

        self.update_prog(0, maximum=len(files))

        for idx, src in enumerate(files, 1):
            self.log(f"[{idx}/{len(files)}] Processing: {src.name}")

            temp_png = self.temp_dir / (src.stem + ".png")
            final_out = self.converted_dir / (src.stem + ".webp")

            self.run_ffmpeg(src, temp_png)
            self.run_cwebp(temp_png, final_out)
            self.update_prog(idx)

    def run_ffmpeg(self, src: Path, out_png: Path):
        filter = self.make_ffmpeg_filter(src)
        if not filter:
            raise RuntimeError("No FFmpeg filters generated")

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(src),
            "-filter_complex",
            filter,
            "-map",
            "[vout]",
            "-frames:v",
            "1",
            str(out_png),
        ]

        si = None
        cf = 0
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cf = subprocess.CREATE_NO_WINDOW

        self.log("  ffmpeg: " + " ".join(cmd), isverbose=True)
        p = subprocess.run(cmd, startupinfo=si, creationflags=cf, capture_output=True, text=True)
        if p.returncode != 0:
            self.log("\n-------- FFmpeg STDERR --------")
            self.log(p.stderr.strip())
            raise RuntimeError(f"FFmpeg failed with exit code {p.returncode}")

    def make_ffmpeg_filter(self, src: Path) -> str:
        def should_blur(img_width: int, img_height: int) -> bool:
            if self.job["game"] == "none" or img_width != self.job["width_from"]:
                return False
            for x, y, w, h in self.job["blur"]:
                if x + w > img_width or y + h > img_height:
                    return False
            return True

        def should_resize(img_width: int) -> bool:
            if self.job["operation"] == "full":
                return img_width > self.job["width_to"]
            return img_width == self.job["width_from"]

        parts: List[str] = []
        parts.append("[0:v]format=rgba[in0]")
        last = "[in0]"

        actual_w, actual_h = self.get_image_dimension(src)

        # blur
        if should_blur(actual_w, actual_h):
            for i, (x, y, w, h) in enumerate(self.job["blur"]):
                parts.append(f"{last}split=2[base{i}][tmp{i}]")
                parts.append(
                    f"[tmp{i}]crop={w}:{h}:{x}:{y},boxblur=min(w\,h)/2:5:min(cw\,ch)/2:5:min(w\,h)/2:5[blur{i}]"  # pyright: ignore[reportInvalidStringEscapeSequence]
                )
                parts.append(f"[base{i}][blur{i}]overlay={x}:{y}[out{i}]")
                last = f"[out{i}]"

        # crop
        crop_h = self.job.get("crop_height", 0)
        pos = self.job.get("crop_pos", "full")

        if pos != "full" and crop_h > 0:
            if pos == "bottom":
                parts.append(f"{last}crop=in_w:{crop_h}:0:in_h-{crop_h}[outc]")
            elif pos == "center":
                parts.append(f"{last}crop=in_w:{crop_h}:0:(in_h-{crop_h})/2[outc]")
            last = "[outc]"

        # resize / final map
        if should_resize(actual_w):
            parts.append(f"{last}scale={self.job['width_to']}:-1:flags=lanczos[vout]")
        else:
            parts.append(f"{last}null[vout]")

        return ";".join(parts)

    def get_image_dimension(self, path: Path) -> tuple[int, int]:
        p = subprocess.run(["get-image-dimension", str(path)], capture_output=True, text=True, check=True)
        width, height = map(int, p.stdout.strip().split(" x "))
        return width, height

    def run_cwebp(self, src_png: Path, out_webp: Path):
        cmd = ["cwebp", "-quiet", "-q", "85", str(src_png), "-o", str(out_webp)]

        si = None
        cf = 0
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cf = subprocess.CREATE_NO_WINDOW

        self.log("  cwebp: " + " ".join(cmd), isverbose=True)
        p = subprocess.run(cmd, startupinfo=si, creationflags=cf, capture_output=True, text=True)
        if p.returncode != 0:
            self.log("-------- cwebp STDERR --------")
            self.log(p.stderr.strip())
            raise RuntimeError(f"cwebp failed with exit code {p.returncode}")

    def cleanup(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.log("Temporary directory removed.")
        if self.job["delete_job_file"]:
            try:
                self.job_file_path.unlink(missing_ok=True)
                self.log("Job file deleted.")
            except Exception as e:
                self.log(f"Failed to delete job file: {e}")


def load_job(path: Path) -> JobFile:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    job_path = Path(sys.argv[1])
    if not job_path.exists():
        sys.exit(1)

    try:
        job = load_job(job_path)

        gui = ConvertScreenshotGUI(job, job_path)
        gui.root.withdraw()
        if gui.check_dependencies():
            gui.root.deiconify()
            gui.run(center=True)
        else:
            gui.root.destroy()
            sys.exit(1)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
