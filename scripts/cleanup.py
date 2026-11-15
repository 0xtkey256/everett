"""Delete only sandboxes labelled app=everett (never anything else)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "orchestrator"))
from daytona import Daytona, DaytonaConfig  # noqa: E402

from everett import config  # noqa: E402

d = Daytona(DaytonaConfig(api_key=config.require("DAYTONA_API_KEY")))
n = 0
for sb in d.list():
    if (getattr(sb, "labels", None) or {}).get("app") == "everett":
        sb.delete()
        n += 1
print(f"deleted {n} everett sandboxes")
