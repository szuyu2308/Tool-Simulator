# core/vision.py

from core.tech import cv2, np, time


class MotionDetector:
    def __init__(
        self,
        diff_threshold=0.003,
        stable_frames=6,
        resize_width=320
    ):
        self.diff_threshold = diff_threshold
        self.stable_frames = stable_frames
        self.resize_width = resize_width

        self.last_frame = None
        self.stable_count = 0

    def _preprocess(self, frame):
        h, w = frame.shape[:2]
        scale = self.resize_width / w
        frame = cv2.resize(frame, (self.resize_width, int(h * scale)))
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return frame

    def update(self, frame) -> bool:
        """
        Trả về True nếu màn hình đã ổn định
        """
        frame = self._preprocess(frame)

        if self.last_frame is None:
            self.last_frame = frame
            return False

        diff = cv2.absdiff(self.last_frame, frame)
        diff_ratio = np.sum(diff > 10) / diff.size

        self.last_frame = frame

        if diff_ratio < self.diff_threshold:
            self.stable_count += 1
        else:
            self.stable_count = 0

        return self.stable_count >= self.stable_frames

class Vision:
    def __init__(self, detectors):
        self.detectors = detectors

    def detect_icon(self, frame, template, region):
        return self.detectors["icon"].detect(frame, template, region)
