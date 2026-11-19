"""AssinaJA FastAPI entry point."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
UPLOADED_LOGO = Path(r"C:\Users\f015114\.gemini\antigravity\brain\4c42f1b7-1a09-4439-913b-076db36a5cf6\.user_uploaded\media_1794427999208_31839dac.png")
if UPLOADED_LOGO.is_file():
    for target in (ROOT / 'frontend' / 'dist' / 'logo-baleia-ia.png', ROOT / 'frontend' / 'public' / 'logo-baleia-ia.png'):
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(UPLOADED_LOGO, target)
        except Exception:
            pass

from backend.launcher import main

if __name__ == "__main__":
    main()
