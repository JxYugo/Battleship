import os
import sys
import time
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def start_hidden(command, env=None):
    return subprocess.Popen(
        command,
        cwd=BASE_DIR,
        env=env,
        creationflags=CREATE_NO_WINDOW,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


server = None
player1 = None
player2 = None

try:
    server = start_hidden([PYTHON, "battleship_server.py"])
    time.sleep(1.5)

    env1 = os.environ.copy()
    env1["BATTLESHIP_WINDOW_POS"] = "40,80"

    env2 = os.environ.copy()
    env2["BATTLESHIP_WINDOW_POS"] = "760,80"

    player1 = start_hidden([PYTHON, "battleship_client.py"], env=env1)
    time.sleep(0.8)

    player2 = start_hidden([PYTHON, "battleship_client.py"], env=env2)

    player1.wait()
    player2.wait()

finally:
    for process in [player1, player2, server]:
        if process and process.poll() is None:
            process.terminate()
