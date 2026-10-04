"""
MonitoringAgent Fetch protocol.

CareBot sends MonitoringRequest.

MonitoringAgent:
    1. loads the latest health snapshot from S3
    2. runs deterministic + Bedrock monitoring logic
    3. converts the Decision into MonitoringResult
    4. returns the result to CareBot

CareBot decides what happens next.
"""

import asyncio

from uagents import (
    Context,
    Field,
    Model,
    Protocol,
)

from aws_io import (
    load_latest_snapshot,
)

from monitor import (
    run_cycle,
)


# ===========================================================================
# MODELS
#
# MUST EXACTLY MATCH CAREBOT.
# ===========================================================================

class MonitoringRequest(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    raw_request: str = Field(
        description="Original natural-language health request from the user"
    )

    health_context: str = Field(
        description="Health information or context supplied by CareBot"
    )


class MonitoringResult(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    condition_summary: str = Field(
        description="Short summary of the monitoring assessment"
    )

    action_required: bool = Field(
        description="Whether an assistive follow-up action may be appropriate"
    )

    recommended_object: str = Field(
        description="Object suggested for retrieval, otherwise empty"
    )

    urgency: str = Field(
        description="Relative urgency such as low, medium, or high"
    )

    status: str = Field(
        description="Monitoring task status"
    )


# ===========================================================================
# PROTOCOL
# ===========================================================================

monitoring_protocol = Protocol(
    name="HealthMonitoring",
    version="1.0",
)


# ===========================================================================
# CAREBOT -> MONITORINGAGENT
# ===========================================================================

@monitoring_protocol.on_message(
    model=MonitoringRequest,
    replies=MonitoringResult,
)
async def handle_monitoring_request(
    ctx: Context,
    sender: str,
    msg: MonitoringRequest,
):

    ctx.logger.info(
        f"Received MonitoringRequest for task {msg.task_id}"
    )

    ctx.logger.info(
        f"User request: {msg.raw_request}"
    )

    ctx.logger.info(
        f"Health context: {msg.health_context}"
    )


    # boto3 + Bedrock are blocking calls.
    try:

        snapshot = await asyncio.to_thread(
            load_latest_snapshot
        )

        ctx.logger.info(
            f"Loaded health snapshot: "
            f"{snapshot.get('snapshot_id')}"
        )


        decision = await asyncio.to_thread(
            run_cycle,
            snapshot,
        )


    except Exception as exc:

        ctx.logger.exception(
            f"Monitoring cycle failed: {exc}"
        )

        await ctx.send(
            sender,
            MonitoringResult(
                task_id=msg.task_id,
                condition_summary=(
                    "The monitoring system could not analyze "
                    "the latest health data."
                ),
                action_required=False,
                recommended_object="",
                urgency="none",
                status="failed",
            ),
        )

        return


    # -----------------------------------------------------------------------
    # MAP MONITORING DECISION -> CAREBOT CONTRACT
    # -----------------------------------------------------------------------

    action = decision.get(
        "action",
        "no_action",
    )

    severity = decision.get(
        "severity",
        "none",
    )

    message = decision.get(
        "message",
        "Monitoring analysis completed.",
    )

    recommended_object = decision.get(
        "spatial_lookup_item"
    )

    if recommended_object is None:
        recommended_object = ""


    action_required = (
        action != "no_action"
    )


    result = MonitoringResult(
        task_id=msg.task_id,
        condition_summary=message,
        action_required=action_required,
        recommended_object=recommended_object,
        urgency=severity,
        status="completed",
    )


    ctx.logger.info(
        f"Monitoring decision: {decision}"
    )

    ctx.logger.info(
        f"Mapped result: "
        f"action_required={action_required}, "
        f"recommended_object={recommended_object}, "
        f"urgency={severity}"
    )


    await ctx.send(
        sender,
        result,
    )


    ctx.logger.info(
        f"MonitoringResult returned to CareBot "
        f"for task {msg.task_id}"
    )