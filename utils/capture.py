import mss
import numpy as np

def capture_region(rect):
    x, y, w, h = rect
    with mss.mss() as sct:
        monitor = {
            "left": x,
            "top": y,
            "width": w,
            "height": h
        }
        img = sct.grab(monitor)
        return np.array(img)
