import asyncio
import os
import tempfile
import time

PREFIX = "diet_photo_"
RETENTION_DAYS = 7


def cleanup_watcher(check_interval: int = 24 * 3600):
    async def _cleanup():
        while True:
            cutoff = time.time() - RETENTION_DAYS * 24 * 3600
            temp_dir = tempfile.gettempdir()
            for name in os.listdir(temp_dir):
                if name.startswith(PREFIX):
                    path = os.path.join(temp_dir, name)
                    try:
                        if os.path.getmtime(path) < cutoff:
                            os.remove(path)
                    except FileNotFoundError:
                        pass
                    except Exception:
                        pass
            await asyncio.sleep(check_interval)
    return _cleanup
