import json
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
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


class App(tk.Tk):
    def __init__(self, job: JobFile, job_file_path: Path):
        super().__init__()

        self.job = job
        self.job_file_path = job_file_path
        self.log_queue = queue.Queue()

        self.target_dir = Path(job["target"])
        self.temp_dir = self.target_dir / "cs-temp"
        self.converted_dir = self.target_dir.parent if job["save_at_parent"] else self.target_dir / "converted"

        self.title(f"ConvertScreenshot - {job['operation']}")
        self.geometry("484x461")
        self.resizable(False, False)

        # log area
        self.text = tk.Text(self, wrap="word", font=("Consolas", 10))
        self.text.pack(fill="both", expand=True)

        self.log(f"Target: {job['target']}")
        self.log(f"Operation: {job['operation']}")
        self.log(f"Game: {job['game']}")
        self.log("")

        self.after(100, self.process_queue)

        t = threading.Thread(target=self.run_job, daemon=True)
        t.start()

    def log(self, msg: str):
        self.log_queue.put(msg)

    def process_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.text.insert("end", msg + "\n")
                self.text.see("end")
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def run_job(self):
        try:
            self.prepare_dirs()
            self.process_images()
            self.log("\nJob finished successfully.")
        except Exception as e:
            self.log(f"\nERROR: {e}")
        finally:
            self.cleanup()
            self.after(15000, self.destroy)

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

        for idx, src in enumerate(files, 1):
            self.log(f"[{idx}/{len(files)}] Processing: {src.name}")

            temp_png = self.temp_dir / (src.stem + ".png")
            final_out = self.converted_dir / (src.stem + ".webp")

            self.run_ffmpeg(src, temp_png)
            self.run_cwebp(temp_png, final_out)

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

    def run_ffmpeg(self, src: Path, out_png: Path):
        filter = self.make_ffmpeg_filter(src)
        if not filter:
            raise RuntimeError("No FFmpeg filters generated")

        cmd = ["ffmpeg", "-y", "-i", str(src), "-filter_complex", filter, "-map", "[vout]", "-frames:v", "1", str(out_png)]

        si = None
        cf = 0
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cf = subprocess.CREATE_NO_WINDOW

        self.log("  ffmpeg: " + " ".join(cmd))  # comment this out in production
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
                parts.append(f"[tmp{i}]crop={w}:{h}:{x}:{y},boxblur=10:1:5:1:0:0[blur{i}]")
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

        self.log("  cwebp: " + " ".join(cmd))  # comment this out in production
        p = subprocess.run(cmd, startupinfo=si, creationflags=cf, capture_output=True, text=True)
        if p.returncode != 0:
            self.log("-------- cwebp STDERR --------")
            self.log(p.stderr.strip())
            raise RuntimeError(f"cwebp failed with exit code {p.returncode}")


def load_job(path: Path) -> JobFile:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        sys.exit(1)

    job_path = Path(sys.argv[1])
    if not job_path.exists():
        sys.exit(1)

    job = load_job(job_path)
    app = App(job, job_path)
    app.mainloop()


if __name__ == "__main__":
    main()
