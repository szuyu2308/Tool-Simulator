"""
ICaptureProvider implementation with BetterCam → DXCam → MSS fallback chain
High-FPS capture with per-worker cache
"""

from typing import Optional, Tuple, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import time
import threading
import numpy as np
from utils.logger import log


@dataclass
class Frame:
    """Captured frame data"""
    pixels: np.ndarray  # BGR or BGRA numpy array
    width: int
    height: int
    timestamp: float  # time.time()
    provider: str  # Which provider captured this frame
    
    @property
    def age(self) -> float:
        """Age of frame in seconds"""
        return time.time() - self.timestamp


class ICaptureProvider(ABC):
    """Abstract capture provider interface"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is available on the system"""
        pass
    
    @abstractmethod
    def grab(self, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        """Capture region at screen coordinates (x, y, w, h)"""
        pass
    
    @abstractmethod
    def release(self):
        """Release resources"""
        pass


class BetterCamProvider(ICaptureProvider):
    """BetterCam capture provider (primary, highest performance)"""
    
    def __init__(self):
        self._camera = None
        self._available = None
    
    @property
    def name(self) -> str:
        return "BetterCam"
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        
        try:
            import bettercam
            self._camera = bettercam.create()
            self._available = True
            log(f"[CAPTURE] BetterCam initialized successfully")
        except ImportError:
            log(f"[CAPTURE] BetterCam not installed")
            self._available = False
        except Exception as e:
            log(f"[CAPTURE] BetterCam init failed: {e}")
            self._available = False
        
        return self._available
    
    def grab(self, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        if not self.is_available() or not self._camera:
            return None
        
        try:
            # BetterCam region format: (left, top, right, bottom)
            region = (x, y, x + w, y + h)
            img = self._camera.grab(region=region)
            
            if img is None:
                return None
            
            # Ensure correct size
            if img.shape[1] != w or img.shape[0] != h:
                img = img[:h, :w]
            
            return Frame(
                pixels=img,
                width=img.shape[1],
                height=img.shape[0],
                timestamp=time.time(),
                provider=self.name
            )
        except Exception as e:
            log(f"[CAPTURE] BetterCam grab error: {e}")
            return None
    
    def release(self):
        if self._camera:
            try:
                self._camera.release()
            except:
                pass
            self._camera = None


class DXCamProvider(ICaptureProvider):
    """DXCam capture provider (fallback)"""
    
    def __init__(self):
        self._camera = None
        self._available = None
    
    @property
    def name(self) -> str:
        return "DXCam"
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        
        try:
            import dxcam
            self._camera = dxcam.create()
            self._available = True
            log(f"[CAPTURE] DXCam initialized successfully")
        except ImportError:
            log(f"[CAPTURE] DXCam not installed")
            self._available = False
        except Exception as e:
            log(f"[CAPTURE] DXCam init failed: {e}")
            self._available = False
        
        return self._available
    
    def grab(self, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        if not self.is_available() or not self._camera:
            return None
        
        try:
            # DXCam region format: (left, top, right, bottom)
            region = (x, y, x + w, y + h)
            img = self._camera.grab(region=region)
            
            if img is None:
                return None
            
            # DXCam returns RGB, convert to BGR for consistency
            if len(img.shape) == 3 and img.shape[2] == 3:
                img = img[:, :, ::-1].copy()
            
            # Ensure correct size
            if img.shape[1] != w or img.shape[0] != h:
                img = img[:h, :w]
            
            return Frame(
                pixels=img,
                width=img.shape[1],
                height=img.shape[0],
                timestamp=time.time(),
                provider=self.name
            )
        except Exception as e:
            log(f"[CAPTURE] DXCam grab error: {e}")
            return None
    
    def release(self):
        if self._camera:
            try:
                del self._camera
            except:
                pass
            self._camera = None


class MSSProvider(ICaptureProvider):
    """MSS capture provider (final fallback, always works)"""
    
    def __init__(self):
        self._sct = None
        self._available = None
    
    @property
    def name(self) -> str:
        return "MSS"
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        
        try:
            import mss
            self._sct = mss.mss()
            self._available = True
            log(f"[CAPTURE] MSS initialized successfully")
        except ImportError:
            log(f"[CAPTURE] MSS not installed")
            self._available = False
        except Exception as e:
            log(f"[CAPTURE] MSS init failed: {e}")
            self._available = False
        
        return self._available
    
    def grab(self, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        if not self.is_available() or not self._sct:
            return None
        
        try:
            monitor = {"left": x, "top": y, "width": w, "height": h}
            sct_img = self._sct.grab(monitor)
            
            # Convert to numpy array (BGRA)
            img = np.array(sct_img)
            
            # Convert BGRA to BGR
            if img.shape[2] == 4:
                img = img[:, :, :3]
            
            return Frame(
                pixels=img,
                width=img.shape[1],
                height=img.shape[0],
                timestamp=time.time(),
                provider=self.name
            )
        except Exception as e:
            log(f"[CAPTURE] MSS grab error: {e}")
            return None
    
    def release(self):
        if self._sct:
            try:
                self._sct.close()
            except:
                pass
            self._sct = None


class CaptureManager:
    """
    Manages capture providers with fallback chain and per-worker cache.
    
    Fallback order (LOCKED):
    1. BetterCam (primary, highest FPS)
    2. DXCam (fallback)
    3. MSS (final fallback, always works)
    
    Cache Policy (LOCKED):
    - Default TTL: 1.0s for most commands
    - Wait polling TTL: 0.1s or force_refresh=True
    """
    
    DEFAULT_TTL = 1.0  # seconds
    WAIT_TTL = 0.1  # seconds for Wait polling
    
    def __init__(self):
        self._providers: list[ICaptureProvider] = []
        self._active_provider: Optional[ICaptureProvider] = None
        self._cache: dict[int, Frame] = {}  # hwnd -> Frame
        self._cache_lock = threading.Lock()
        
        self._init_providers()
    
    def _init_providers(self):
        """Initialize providers in fallback order"""
        # Order matters! BetterCam → DXCam → MSS
        self._providers = [
            BetterCamProvider(),
            DXCamProvider(),
            MSSProvider()
        ]
        
        # Find first available provider
        for provider in self._providers:
            if provider.is_available():
                self._active_provider = provider
                log(f"[CAPTURE] Active provider: {provider.name}")
                break
        
        if not self._active_provider:
            log(f"[CAPTURE] WARNING: No capture provider available!")
    
    def get_frame(self, hwnd: int, x: int, y: int, w: int, h: int,
                  force_refresh: bool = False, ttl: float = None) -> Optional[Frame]:
        """
        Get frame for emulator instance with caching.
        
        Args:
            hwnd: Window handle (used as cache key)
            x, y, w, h: Screen coordinates of client area
            force_refresh: Skip cache and capture fresh
            ttl: Custom TTL (default: DEFAULT_TTL)
        
        Returns:
            Frame or None
        """
        if ttl is None:
            ttl = self.DEFAULT_TTL
        
        with self._cache_lock:
            # Check cache
            if not force_refresh and hwnd in self._cache:
                cached = self._cache[hwnd]
                if cached.age < ttl:
                    return cached
            
            # Capture new frame
            frame = self._capture(x, y, w, h)
            
            if frame:
                self._cache[hwnd] = frame
                return frame
            
            # Return stale cache if capture failed
            if hwnd in self._cache:
                log(f"[CAPTURE] Using stale cache for hwnd={hwnd}")
                return self._cache[hwnd]
            
            return None
    
    def _capture(self, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        """Capture using active provider with fallback"""
        if self._active_provider:
            frame = self._active_provider.grab(x, y, w, h)
            if frame:
                return frame
        
        # Fallback chain
        for provider in self._providers:
            if provider == self._active_provider:
                continue
            
            if provider.is_available():
                frame = provider.grab(x, y, w, h)
                if frame:
                    # Switch to this provider
                    log(f"[CAPTURE] Switching to fallback: {provider.name}")
                    self._active_provider = provider
                    return frame
        
        return None
    
    def get_frame_for_wait(self, hwnd: int, x: int, y: int, w: int, h: int) -> Optional[Frame]:
        """Get fresh frame for Wait polling (short TTL or force refresh)"""
        return self.get_frame(hwnd, x, y, w, h, force_refresh=True)
    
    def clear_cache(self, hwnd: int = None):
        """Clear cache for specific hwnd or all"""
        with self._cache_lock:
            if hwnd:
                self._cache.pop(hwnd, None)
            else:
                self._cache.clear()
    
    def release(self):
        """Release all providers"""
        for provider in self._providers:
            provider.release()
        self._providers.clear()
        self._active_provider = None
        self._cache.clear()
    
    @property
    def active_provider_name(self) -> str:
        return self._active_provider.name if self._active_provider else "None"


# Global capture manager singleton
_capture_manager: Optional[CaptureManager] = None


def get_capture_manager() -> CaptureManager:
    """Get or create global capture manager"""
    global _capture_manager
    if _capture_manager is None:
        _capture_manager = CaptureManager()
    return _capture_manager
