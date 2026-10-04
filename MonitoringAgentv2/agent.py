"""
Local MonitoringAgent.

Runs locally because monitoring requires:
    boto3
    S3
    Amazon Bedrock

Agentverse Mailbox connects it to hosted CareBot.
"""

import asyncio
import os

from dotenv import load_dotenv

from uagents import (
    Agent,
    Context,
)

from protocols import (
    monitoring_protocol,
)


# ===========================================================================
# ENVIRONMENT
# ===========================================================================

load_dotenv()


MONITORING_AGENT_SEED = os.getenv(
    "MONITORING_AGENT_SEED"
)


if not MONITORING_AGENT_SEED:

    raise RuntimeError(
        "MONITORING_AGENT_SEED environment variable is not set"
    )


# ===========================================================================
# PYTHON 3.14 EVENT LOOP
# ===========================================================================

loop = asyncio.new_event_loop()

asyncio.set_event_loop(
    loop
)


# ===========================================================================
# AGENT
# ===========================================================================

agent = Agent(
    name="monitoring-agent",
    seed=MONITORING_AGENT_SEED,
    port=8003,
    mailbox=True,
    loop=loop,
)


# ===========================================================================
# PROTOCOL
# ===========================================================================

agent.include(
    monitoring_protocol,
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
        f"MonitoringAgent address: {agent.address}"
    )

    ctx.logger.info(
        f"HealthMonitoring protocol digest: "
        f"{monitoring_protocol.digest}"
    )


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == "__main__":

    agent.run()