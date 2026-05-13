"""TLDE — Too Long Didn't Emulate.

Entry point for the firmware emulation pipeline.

Usage:
    uv run tlde <pdf_path> [pdf_path ...]
    uv run python -m tlde <pdf_path> [pdf_path ...]
"""

import asyncio
import sys

from tlde.pipeline.firmware_emulation import main


if __name__ == "__main__":
    asyncio.run(main())
