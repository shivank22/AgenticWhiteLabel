"""Run the DICE workflow chat UI."""

from __future__ import annotations

import logging

import uvicorn

from src.config.settings import get_settings


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    host = settings.web_host
    port = settings.web_port
    logging.getLogger("src.api").info("DICE workflow UI at http://%s:%s", host, port)
    uvicorn.run(
        "src.api.app:create_app",
        factory=True,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
