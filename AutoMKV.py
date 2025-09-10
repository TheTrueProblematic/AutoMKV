"""
Auto MKV — Refactored
- Reliability, readability, maintainability improved
- AWS SES removed; Home Assistant notifications added
- Primary functionality and UI preserved

Requirements:
  pip install psutil requests
Environment:
  HOME_ASSISTANT_BASE_URL = e.g. http://homeassistant.local:8123
  HOME_ASSISTANT_TOKEN    = Long-Lived Access Token from Home Assistant profile

Notify entities used (unchanged behavior, new backend):
  - notify.mobile_app_prometheus (Matt)
  - notify.mobile_app_promaxeus  (Max)
"""
from __future__ import annotations

import os
import time
import random
import threading
import subprocess
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import psutil
import requests
from tkinter import *  # UI preserved as-is

# ----------------------------- Configuration ---------------------------------

# Paths / commands
MAKEMKV = Path(r"C:/Program Files (x86)/MakeMKV/makemkvcon64.exe")
RIP_DEST = Path(r"T:/Shared/MoviesTBC")
BLURAY_DRIVE = "D:"  # Drive letter the app watches

# Timings
POLL_WHEN_RUNNING_SEC = 10
POLL_WHEN_STOPPED_SEC = 1
POST_INSERT_DELAY_SEC = 20
AWAIT_EJECT_POLL_SEC = 5

# Home Assistant
HA_BASE_URL = os.getenv("HOME_ASSISTANT_BASE_URL", "")
HA_TOKEN = os.getenv("HOME_ASSISTANT_TOKEN", "")
HA_ENTITY_MATT = "notify.mobile_app_prometheus"
HA_ENTITY_MAX = "notify.mobile_app_promaxeus"
HTTP_TIMEOUT = 10

# ------------------------------- Logging -------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("automkv")

# ------------------------------ Globals (UI) ---------------------------------

# Keep these global names and behavior to preserve UI semantics
guiStatus = 1
NotificationLevel = 1  # 1=Both, 2=Matt, 3=Max (same meaning as original)
running = False
recordTime = time.time()

# ------------------------------ Utilities ------------------------------------

def space_to_underscore(s: str) -> str:
    return s.replace(" ", "_")


def underscore_to_space(s: str) -> str:
    return s.replace("_", " ")


def is_bluray_drive(drive: str) -> bool:
    """Return True if the drive exists and is mountable."""
    try:
        # On Windows, a present disc should make disk_usage work
        psutil.disk_usage(drive)
        return True
    except Exception:
        return False


def find_text_after_search(search: str, text: str) -> str:
    """Extract text immediately after `search` up to the next double quote."""
    start_index = text.find(search)
    if start_index == -1:
        return ""
    start_index += len(search)
    end_index = text.find('"', start_index)
    if end_index == -1:
        return ""
    return text[start_index:end_index]


def largest_only(path: Path) -> int:
    """Ensure only the largest file(s) remain in `path`.
    Returns count of largest files left (>=1) or 0 if path missing/empty.
    """
    if not path.exists():
        log.error("The specified path does not exist: %s", path)
        return 0
    files = [p for p in path.iterdir() if p.is_file()]
    if not files:
        return 0
    if len(files) == 1:
        return 1
    files_sorted = sorted(files, key=lambda p: p.stat().st_size, reverse=True)
    max_size = files_sorted[0].stat().st_size
    largest = [p for p in files_sorted if p.stat().st_size == max_size]
    to_delete = [p for p in files_sorted if p not in largest]
    for f in to_delete:
        try:
            f.unlink()
            log.info("Deleted file: %s", f.name)
        except Exception as e:
            log.warning("Failed to delete %s: %s", f, e)
    return len(largest)


def rand_delete_except_one(path: Path) -> None:
    files = [p for p in path.iterdir() if p.is_file()]
    if len(files) <= 1:
        log.error("ERROR: The folder must contain more than one file.")
        completed(False, path.name)
        return
    keep = random.choice(files)
    log.info("Keeping file: %s", keep.name)
    for f in files:
        if f != keep:
            try:
                f.unlink()
                log.info("Deleted file: %s", f.name)
            except Exception as e:
                log.warning("Failed to delete %s: %s", f, e)


# --------------------------- Home Assistant Notify ---------------------------

@dataclass
class HAClient:
    base_url: str
    token: str

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def call_service(self, domain: str, service: str, data: dict) -> bool:
        if not self.base_url or not self.token:
            log.error("Home Assistant not configured. Set HOME_ASSISTANT_BASE_URL and HOME_ASSISTANT_TOKEN.")
            return False
        url = f"{self.base_url.rstrip('/')}/api/services/{domain}/{service}"
        try:
            r = requests.post(url, json=data, headers=self._headers(), timeout=HTTP_TIMEOUT)
            if r.ok:
                return True
            log.error("HA call failed (%s): %s", r.status_code, r.text)
            return False
        except requests.RequestException as e:
            log.error("HA call exception: %s", e)
            return False


class Notifier:
    def __init__(self, ha: HAClient) -> None:
        self.ha = ha

    def _notify_entity(self, entity: str, message: str, title: str = "Status") -> None:
        # notify.* lives under domain "notify"; service name is the entity after the dot
        try:
            domain = "notify"
            service = entity.split(".", 1)[1]
        except Exception:
            log.error("Invalid notify entity: %s", entity)
            return
        payload = {"message": message, "title": title}
        ok = self.ha.call_service(domain, service, payload)
        if ok:
            log.info("Sent HA notification to %s", entity)

    def notify(self, success: bool, title: str, level: int) -> None:
        """Mirror original logic: level 1=both, 2=Matt, 3=Max."""
        succ = f"{title} was ripped successfully!"
        fail = f"{title} failed."
        msg = succ if success else fail

        targets = []
        if level == 1:
            targets = [HA_ENTITY_MATT, HA_ENTITY_MAX]
        elif level == 2:
            targets = [HA_ENTITY_MATT]
        elif level == 3:
            targets = [HA_ENTITY_MAX]
        else:
            targets = [HA_ENTITY_MATT, HA_ENTITY_MAX]  # safe default

        for ent in targets:
            self._notify_entity(ent, msg, "Status")


ha_client = HAClient(HA_BASE_URL, HA_TOKEN)
notifier = Notifier(ha_client)

# ------------------------------- Core Logic ----------------------------------


def run_makemkv_info() -> str:
    cmd = f'"{MAKEMKV}" -r info disk:0'
    log.info("Running: %s", cmd)
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.returncode != 0:
        log.error("makemkv info failed: rc=%s, err=%s", result.returncode, result.stderr)
    return result.stdout


def run_makemkv_rip(output_dir: Path) -> tuple[int, str]:
    # Keep the command identical to previous behavior (all titles)
    cmd = f'"{MAKEMKV}" mkv disc:0 all {str(output_dir)}'
    log.info("Running: %s", cmd)
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.stdout:
        print("Rip Report:")
        print(result.stdout)
    return result.returncode, result.stdout


def parse_disc_title(info_stdout: str) -> str:
    # Preserve prior parsing behavior using the same search token
    searchTerm = '1WL","'
    title = find_text_after_search(searchTerm, info_stdout)
    return underscore_to_space(title)


def rename_single_file(folder: Path, new_name: str) -> bool:
    files = [p for p in folder.iterdir() if p.is_file()]
    if len(files) != 1:
        return False
    src = files[0]
    dst = folder / new_name
    try:
        src.rename(dst)
        return True
    except Exception as e:
        log.error("Rename failed: %s", e)
        return False


def await_eject() -> None:
    print("Processing complete. Waiting for disk to be ejected...")
    while is_bluray_drive(BLURAY_DRIVE):
        time.sleep(AWAIT_EJECT_POLL_SEC)
    print("Disk ejected. Ready for a new disk.")


def completed(success: bool, title: str) -> None:
    global NotificationLevel
    if success:
        print("Completed successfully.")
    else:
        print("Failed to complete successfully.")
    notifier.notify(success, title, NotificationLevel)
    await_eject()


def processFile() -> None:
    global guiStatus

    print("Disk inserted. Processing files...")
    guiStatus = 3
    update_status()

    try:
        info_out = run_makemkv_info()
        print("Drive List:")
        print(info_out)
        title = parse_disc_title(info_out)
        work_dir = RIP_DEST / space_to_underscore(title)
        print(f"Title: {title}")
        print(f"Work Folder: {work_dir}")
        work_dir.mkdir(parents=True, exist_ok=True)

        rc, _ = run_makemkv_rip(work_dir)
        if rc != 0:
            print("Rip failed with return code:", rc)
            completed(False, title)
            return
        else:
            print("Rip was successful.")

        num_largest = largest_only(work_dir)
        if num_largest != 1:
            try:
                # Fallback to random deletion to ensure one file left (match original behavior)
                print(f"{num_largest} files remain...Deleting Randomly")
                rand_delete_except_one(work_dir)
            except Exception as e:
                log.error("Random delete failed: %s", e)

        titlefile = f"{title}.mkv"
        if rename_single_file(work_dir, titlefile):
            completed(True, title)
        else:
            completed(False, title)

    except Exception as e:
        log.exception("Unhandled error in processFile: %s", e)
        completed(False, "Unknown Title")


# ------------------------------- UI (Tkinter) --------------------------------

root = Tk()
root.title("Auto MKV")
root.geometry('700x600')

menu = Menu(root)
item = Menu(menu, tearoff=0)
item.add_command(label='Max', command=lambda: setLevel(3))
item.add_command(label='Matt', command=lambda: setLevel(2))
item.add_command(label='Both', command=lambda: setLevel(1))
menu.add_cascade(label='Notifications', menu=item)
root.config(menu=menu)

title_lbl = Label(root, text="Auto MKV", font=("Arial", 40), fg="#003366")
title_lbl.grid(column=0, row=0, columnspan=3, pady=30)

button_frame = Frame(root)
button_frame.grid(column=0, row=1, columnspan=3, pady=30)

stop_btn = Button(button_frame, text="Stop", fg="red", bg="black", font=("Arial", 24), width=10, height=2, command=lambda: stop())
stop_btn.pack(side=LEFT, padx=20)

start_btn = Button(button_frame, text="Start", fg="green", bg="black", font=("Arial", 24), width=10, height=2, command=lambda: start())
start_btn.pack(side=RIGHT, padx=20)

status_frame = Frame(root, bd=2, relief="solid")
status_frame.grid(column=0, row=2, columnspan=3, padx=50, pady=30, sticky="ew")

status_label = Label(status_frame, text="", font=("Arial", 18), padx=10, pady=10)
status_label.pack(fill="both", expand=True)

root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)
root.grid_columnconfigure(2, weight=1)
root.grid_rowconfigure(0, weight=1)
root.grid_rowconfigure(1, weight=1)
root.grid_rowconfigure(2, weight=1)


def update_status() -> None:
    global guiStatus
    messages = {
        1: "Ready",
        2: "Running...",
        3: "Disk inserted. Processing files...",
        4: "Stopping...",
        5: "Notification Status Updated",
        6: "This is a longer message to make sure that a longer message can still fit.",
        7: "Starting...",
    }
    status_label.config(text=messages.get(guiStatus, "Unknown status"))


# ---------------------------- UI callbacks (same) ----------------------------


def levelSetError():
    print("Level Set Error")


def setLevel(level: int) -> None:
    global guiStatus, NotificationLevel
    if guiStatus != 2:
        print(f"Notification level set to {level}")
        guiStatus = 5
        NotificationLevel = level
        update_status()
    else:
        levelSetError()


def start() -> None:
    global guiStatus, running
    running = True
    guiStatus = 7
    update_status()


def stop() -> None:
    global guiStatus, running
    running = False
    guiStatus = 4
    update_status()


# ------------------------------- Main Loop -----------------------------------


def loop() -> None:
    global running, guiStatus, recordTime
    delayCheck = True

    print("Monitoring started. Waiting for disk insertion...")

    try:
        while True:
            if running:
                guiStatus = 2
                update_status()
                if is_bluray_drive(BLURAY_DRIVE):
                    print(f"{BLURAY_DRIVE} is a Blu-ray drive and is ready. Processing disk...")
                    time.sleep(POST_INSERT_DELAY_SEC)
                    processFile()
                    print("Waiting for next disk...")
                else:
                    print("No disk inserted. Checking again in 10 seconds.")
                time.sleep(POLL_WHEN_RUNNING_SEC)
            else:
                if guiStatus == 5:
                    if delayCheck:
                        recordTime = time.time()
                        delayCheck = False
                    else:
                        passed = time.time() - recordTime
                        if passed > 5:
                            delayCheck = True
                            guiStatus = 1
                            update_status()
                else:
                    guiStatus = 1
                    update_status()
                time.sleep(POLL_WHEN_STOPPED_SEC)
            # Keep status fresh
            update_status()

    except KeyboardInterrupt:
        print("Monitoring interrupted by user.")
    finally:
        print("AutoMKV stopped.")


def gui() -> None:
    root.mainloop()


def main() -> None:
    try:
        t1 = threading.Thread(target=loop, args=())
        t1.start()
        gui()
        t1.join()
    except KeyboardInterrupt:
        print("Monitoring interrupted by user.")
    finally:
        print("AutoMKV stopped.")


if __name__ == "__main__":
    main()
