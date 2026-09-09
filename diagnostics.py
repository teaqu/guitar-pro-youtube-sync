"""Offline packaged-app smoke test and opt-in public-service end-to-end test.

Neither mode reads browser cookies or saved user preferences.
"""

import functools
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import yt_dlp
import yt_dlp_ejs
import gen_gp
from sync import _download_audio, download_youtube_audio, fetch_video_points, select_video_entry, sync_gp_file
from utils import get_ffmpeg_dir, get_js_runtimes


def _run(command: list[str]) -> str:
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(f"{command[0]} failed: {result.stderr[-2000:]}")
    return result.stdout


def _dependencies() -> str:
    print(f"Python {sys.version.split()[0]}; yt-dlp {yt_dlp.version.__version__}; EJS {yt_dlp_ejs.version}")
    deno = get_js_runtimes()["deno"].get("path") or shutil.which("deno")
    if not deno:
        raise RuntimeError("Deno is missing. Install Deno 2.3+ or use a rebuilt executable.")
    print(_run([deno, "--version"]).strip())
    # Check actual JavaScript execution, not just the presence of an executable.
    if _run([deno, "eval", "console.log(6 * 7)"]).strip() != "42":
        raise RuntimeError("Deno could not execute JavaScript")
    for name in ("core.min.js", "lib.min.js"):
        if not files("yt_dlp_ejs.yt.solver").joinpath(name).read_bytes():
            raise RuntimeError(f"Missing EJS solver resource: {name}")
    directory = get_ffmpeg_dir()
    suffix = ".exe" if sys.platform == "win32" else ""
    executables = {}
    for name in ("ffmpeg", "ffprobe"):
        executable = str(Path(directory) / (name + suffix)) if directory else shutil.which(name)
        if not executable:
            raise RuntimeError(f"{name} is missing")
        print(_run([executable, "-version"]).splitlines()[0])
        executables[name] = executable
    return executables["ffprobe"]


def _validate_output(output: Path, audio: Path, probe: str, expected_duration=None):
    info = json.loads(_run([probe, "-v", "error", "-show_entries", "format=duration",
                            "-of", "json", str(audio)]))
    duration = float(info["format"]["duration"])
    if duration <= 0 or (expected_duration is not None and abs(duration - expected_duration) > 0.2):
        raise RuntimeError(f"Unexpected converted/trimmed audio duration: {duration}")
    with ZipFile(output) as archive:
        if archive.testzip():
            raise RuntimeError("Corrupt GP archive")
        root = ET.fromstring(archive.read("Content/score.gpif"))
        embedded = root.findtext("Assets/Asset/EmbeddedFilePath")
        if not embedded or archive.read(embedded) != audio.read_bytes():
            raise RuntimeError("Generated GP does not contain the expected audio")
        if root.find("BackingTrack") is None or not any(
            element.text == "SyncPoint" for element in root.findall(".//Automation/Type")
        ):
            raise RuntimeError("Generated GP is missing its backing track or sync points")
    print(f"Validated GP with embedded audio ({duration:.2f}s)")


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def run_self_test(live: bool = False):
    """Fail loudly on missing dependencies or a broken download-to-GP pipeline."""
    probe = _dependencies()
    with tempfile.TemporaryDirectory(prefix="guitar sync test ") as directory:
        folder = Path(directory)
        gp = folder / "source.gp"
        audio = folder / "audio.mp3"
        output = folder / "synced.gp"
        if live:
            meta, tracks = gen_gp.fetch_all_tracks(23152)
            gen_gp.generate_gp(tracks, gp, meta)
            entry = select_video_entry(fetch_video_points(23152, meta["revisionId"]))
            points = entry["points"]
            download_youtube_audio(entry["videoId"], audio, trim_start=points[0])
        else:
            tracks = [{"name": "Test guitar", "instrumentId": 25, "strings": 6,
                       "tuning": [64, 59, 55, 50, 45, 40],
                       "measures": [{"voices": [{"beats": [
                           {"type": 4, "notes": [{"fret": 0, "string": 0}]}
                           for _ in range(4)]}]}]}]
            gen_gp.generate_gp(tracks, gp, {"artist": "Self test", "title": "Local audio"})
            with wave.open(str(folder / "source.wav"), "wb") as wav:
                wav.setparams((1, 2, 44100, 0, "NONE", "not compressed"))
                wav.writeframes(b"\x00\x00" * 44100 * 3)
            server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_QuietHandler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                _download_audio(f"http://127.0.0.1:{server.server_port}/source.wav", audio, trim_start=1.0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            points = [0.0, 2.0]
        if not audio.is_file() or audio.stat().st_size == 0:
            raise RuntimeError("Download did not produce audio")
        sync_gp_file(gp, points, output, mp3_path=audio)
        _validate_output(output, audio, probe, expected_duration=None if live else 2.0)
    print("LIVE TEST PASSED" if live else "SELF-TEST PASSED")
