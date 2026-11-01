from __future__ import annotations

import json
from pathlib import Path

from ssscreen_web.main import app


def main() -> None:
    output = Path(__file__).with_name("openapi.json")
    output.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
