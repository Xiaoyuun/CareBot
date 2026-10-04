from uagents import Agent, Context

from protocols import action_protocol


# ===========================================================================
# CREATE AGENT
# ===========================================================================

agent = Agent()


# ===========================================================================
# INCLUDE PROTOCOL
# ===========================================================================

agent.include(
    action_protocol,
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
        f"ActionAgent address: {agent.address}"
    )

    ctx.logger.info(
        f"MovementDelegation protocol digest: {action_protocol.digest}"
    )


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == "__main__":
    agent.run()