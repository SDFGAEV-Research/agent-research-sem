from __future__ import annotations
from pathlib import Path

try:
    import fcntl  # POSIX/Ubuntu production path
except ImportError:  # pragma: no cover
    fcntl=None

class ForensicWriterBusy(RuntimeError): pass

class ForensicWriterLease:
    """Kernel-backed single-writer lease for authoritative forensic state and index activation."""
    def __init__(self,path:Path)->None: self.path=path; self._fh=None
    def acquire(self)->"ForensicWriterLease":
        if fcntl is None: raise RuntimeError("kernel forensic writer lease requires fcntl on this platform")
        self.path.parent.mkdir(parents=True,exist_ok=True); fh=self.path.open("a+b")
        try: fcntl.flock(fh.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc: fh.close(); raise ForensicWriterBusy(f"forensic writer lease is held: {self.path}") from exc
        self._fh=fh; return self
    def release(self)->None:
        if self._fh is None: return
        fcntl.flock(self._fh.fileno(),fcntl.LOCK_UN); self._fh.close(); self._fh=None
    def __enter__(self): return self.acquire()
    def __exit__(self,*exc): self.release()
