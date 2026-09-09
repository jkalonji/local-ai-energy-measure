import time
from pynvml import *

nvmlInit()
h = nvmlDeviceGetHandleByIndex(0)
energie_wh = 0.0
t0 = time.time()

try:
    while True:
        p = nvmlDeviceGetPowerUsage(h) / 1000  # mW -> W
        time.sleep(1)
        energie_wh += p * (1 / 3600)
        duree = time.time() - t0
        print(f"\r{p:6.1f} W  |  {energie_wh:8.4f} Wh  |  "
              f"moy {energie_wh * 3600 / duree:6.1f} W  |  "
              f"{duree / 60:5.1f} min", end="")
except KeyboardInterrupt:
    print(f"\nTotal : {energie_wh / 1000:.4f} kWh")