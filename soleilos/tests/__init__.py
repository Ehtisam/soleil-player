"""SoleilOS testleri.

  cd soleilos
  python -m tests               # hepsi
  python -m tests -v            # ayrıntılı

Testler kullanıcı verisine dokunmaz: ~/.soleil yerine geçici bir klasör
kullanılır (SOLEIL_HOME), pencere açılmaz, ses çıkmaz, gerçek mikrofon
açılmaz, internete çıkılmaz (radyo ve sözler testlerde kapalı).

`python -m unittest` doğrudan kullanılmasın: test aracı uygulama paketini
bu dosyadan önce yükleyebiliyor ve o zaman yollar gerçek ~/.soleil'i
gösteriyor. Bu durumda aşağıdaki kilit testleri hiç başlatmaz.
"""

import atexit
import os
import shutil
import sys
import tempfile

if "soleil.config" in sys.modules:
    raise RuntimeError(
        "soleil testlerden önce yüklenmiş; testler gerçek ~/.soleil klasörüne yazabilirdi. "
        "Testleri `python -m tests` ile çalıştır.")

# soleil.config içe aktarılmadan önce ayarlanmalı
TEST_HOME = tempfile.mkdtemp(prefix="soleil-test-")
os.environ["SOLEIL_HOME"] = TEST_HOME
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
atexit.register(shutil.rmtree, TEST_HOME, ignore_errors=True)

from soleil import config  # noqa: E402

assert str(config.DATA) == TEST_HOME, "test klasörü ayarlanamadı"


def clean_home() -> None:
    """Testler arasında kullanıcı verisini sıfırlar (sadece test klasöründe)."""
    for name in os.listdir(TEST_HOME):
        path = os.path.join(TEST_HOME, name)
        shutil.rmtree(path, ignore_errors=True) if os.path.isdir(path) else os.remove(path)
