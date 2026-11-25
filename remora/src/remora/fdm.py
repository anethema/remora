"""Own one firmware child and drive its lockstep JSON actuator/IMU interface."""

# AP_FLAKE8_CLEAN
import csv
import json
import socket
import struct
import subprocess
import sys
from pathlib import Path

from .plant import Plant

FRAME = struct.Struct("<HHI16H")


def run(config, firmware):
    plant = Plant(config)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 9002))
        sock.settimeout(1)
        # The namespace has only loopback. Child lifetime follows this process
        # even when the outer controller is killed.
        with subprocess.Popen(["setpriv", "--pdeathsig", "KILL", *firmware]) as child, open("plant.csv", "w") as log:
            previous, response, next_sample = None, None, 0.0
            series = csv.DictWriter(log, fieldnames=["frame", "pwm1", "pwm3", *plant.metrics()])
            series.writeheader()
            try:
                while child.poll() is None:
                    try:
                        packet, addr = sock.recvfrom(256)
                    except socket.timeout:
                        continue
                    if len(packet) != FRAME.size:
                        raise ValueError("Unexpected SITL actuator packet size")
                    magic, rate, frame, *pwm = FRAME.unpack(packet)
                    if magic != 18458 or not 50 <= rate <= 4000:
                        raise ValueError(f"Unexpected actuator header {magic}, {rate}")
                    if previous is None or frame != previous:
                        if previous is not None and frame != (previous + 1) % 2**32:
                            raise ValueError("SITL restarted or dropped an actuator frame; reset the run")
                        sensors = plant.step(pwm[0], pwm[2], 1.0 / rate)
                        response = ("\n" + json.dumps(sensors) + "\n").encode()
                        previous = frame
                        if plant.t >= next_sample:
                            metrics = plant.metrics()
                            Path("plant.tmp").write_text(json.dumps(metrics))
                            Path("plant.tmp").replace("plant.json")
                            series.writerow(dict(frame=frame, pwm1=pwm[0], pwm3=pwm[2], **metrics))
                            log.flush()
                            next_sample = plant.t + 0.5
                    sock.sendto(response, addr)
                return child.returncode
            finally:
                if child.poll() is None:
                    child.terminate()


if __name__ == "__main__":
    raise SystemExit(run(json.loads(Path(sys.argv[1]).read_text()), sys.argv[2:]))
