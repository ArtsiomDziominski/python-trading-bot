import asyncio
import logging

from app.bot_engine.supervisor import supervisor_loop
from app.core.logging import setup_logging

logging.basicConfig(level=logging.INFO)
setup_logging()
log = logging.getLogger(__name__)


def main() -> None:
    log.info("bot-engine supervisor starting")
    asyncio.run(supervisor_loop())


if __name__ == "__main__":
    main()
