import cv2

class IconDetector:
    def __init__(self, threshold=0.85):
        self.threshold = threshold

    def detect(self, screen, template, region=None):
        """
        region = (x1, y1, x2, y2) theo pixel
        """
        if region:
            x1, y1, x2, y2 = region
            screen = screen[y1:y2, x1:x2]

        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= self.threshold:
            return {
                "found": True,
                "pos": max_loc,
                "score": round(max_val, 3)
            }

        return {"found": False}
