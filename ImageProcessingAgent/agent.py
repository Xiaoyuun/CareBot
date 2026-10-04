import asyncio
import os

from dotenv import load_dotenv
from uagents import Agent, Context

from protocols import image_protocol


load_dotenv()


# ===========================================================================
# CREATE EVENT LOOP
#
# Python 3.14 no longer creates one implicitly.
# ===========================================================================

loop = asyncio.new_event_loop()

asyncio.set_event_loop(loop)


# ===========================================================================
# LOAD PRIVATE SEED
# ===========================================================================

IMAGE_AGENT_SEED = os.getenv(
    "IMAGE_AGENT_SEED"
)

if not IMAGE_AGENT_SEED:
    raise RuntimeError(
        "IMAGE_AGENT_SEED environment variable is not set"
    )


# ===========================================================================
# CREATE AGENT
# ===========================================================================

agent = Agent(
    name="image-processing-agent",
    seed=IMAGE_AGENT_SEED,
    port=8002,
    mailbox=True,
    loop=loop,
)


# ===========================================================================
# INCLUDE PROTOCOL
# ===========================================================================

agent.include(
    image_protocol,
    publish_manifest=True,
)


# ===========================================================================
# STARTUP
# ===========================================================================

@agent.on_event("startup")
async def startup(
    ctx: Context,
):

    ctx.logger.info(
        f"ImageProcessingAgent address: {agent.address}"
    )

    ctx.logger.info(
        f"ImageProcessing protocol digest: {image_protocol.digest}"
    )


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == "__main__":
    agent.run()