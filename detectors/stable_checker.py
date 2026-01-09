import cv2

class StableChecker:
    def __init__(self, diff_threshold=2, stable_count=3):
        self.last_frame = None
        self.counter = 0
        self.diff_threshold = diff_threshold
        self.stable_count = stable_count

    def is_stable(self, frame):
        if self.last_frame is None:
            self.last_frame = frame
            return False

        diff = cv2.absdiff(self.last_frame, frame)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        non_zero = cv2.countNonZero(gray)

        if non_zero < self.diff_threshold:
            self.counter += 1
        else:
            self.counter = 0

        self.last_frame = frame
        return self.counter >= self.stable_count

    def reset(self):
        self.last_frame = None
        self.counter = 0