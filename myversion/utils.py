import os, time, glob

TMP_PATH = os.path.join(os.path.dirname(__file__), 'tmp')
os.makedirs(TMP_PATH, exist_ok=True)

def err(msg: str, code: int = 400):
    """Return error JSON and log to tmp (max 20 files)."""
    # Delete oldest if 20+ files exist
    files = sorted(glob.glob(f"{TMP_PATH}/err_*.txt"))
    while len(files) >= 20:
        os.remove(files.pop(0))
    # Write new error file
    with open(f"{TMP_PATH}/err_{int(time.time()*1000)}.txt", "w") as f:
        f.write(f"{time.ctime()}\n{msg}\n")
    return {"error": msg}, code
