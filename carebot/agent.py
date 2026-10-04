"""
CareBot entry point.

Every specialist response comes back here.

After each response:
    specialist
        -> CareBot
        -> ASI:One reasoning
        -> user progress message
        -> next specialist / finish
"""

from uagents import Agent, Context

from protocols import (
    ActionResult,
    ImageProcessingResult,
    MonitoringResult,
    action_protocol,
    chat_protocol,
    execute_decision,
    get_task_state,
    image_protocol,
    monitoring_protocol,
    reason_about_state,
    save_task_state,
    send_user_update,
)


# ===========================================================================
# AGENT
# ===========================================================================

agent = Agent()


agent.include(
    chat_protocol,
    publish_manifest=True,
)

agent.include(
    monitoring_protocol,
    publish_manifest=True,
)

agent.include(
    image_protocol,
    publish_manifest=True,
)

agent.include(
    action_protocol,
    publish_manifest=True,
)


# ===========================================================================
# COMMON SPECIALIST RESULT HANDLER
# ===========================================================================

async def process_specialist_result(
    ctx: Context,
    task_id: str,
    result: dict,
):

    state = get_task_state(
        ctx,
        task_id,
    )


    if not state:

        ctx.logger.warning(
            f"Received result for unknown task {task_id}"
        )

        return


    state["events"].append(
        result
    )


    save_task_state(
        ctx,
        task_id,
        state,
    )


    try:

        decision = reason_about_state(

            ctx=ctx,

            task_id=task_id,

            latest_result=result,
        )


        ctx.logger.info(
            f"CareBot decision after specialist result: {decision}"
        )


    except Exception as exc:

        ctx.logger.exception(
            f"ASI:One reasoning failed: {exc}"
        )


        await send_user_update(
            ctx,
            task_id,
            "I received the latest result, but I had trouble deciding what to do next.",
        )


        return


    message = decision.get(
        "user_message",
        "I've received the latest result.",
    )


    await send_user_update(
        ctx,
        task_id,
        message,
    )


    try:

        await execute_decision(
            ctx,
            task_id,
            decision,
        )


    except Exception as exc:

        ctx.logger.exception(
            f"Failed to execute next step: {exc}"
        )


        await send_user_update(
            ctx,
            task_id,
            "I received the result, but I couldn't start the next step.",
        )


# ===========================================================================
# MONITORINGAGENT -> CAREBOT
# ===========================================================================

@agent.on_message(
    model=MonitoringResult
)
async def handle_monitoring_result(
    ctx: Context,
    sender: str,
    msg: MonitoringResult,
):

    ctx.logger.info(
        f"Received MonitoringResult for task {msg.task_id}"
    )

    ctx.logger.info(
        f"Condition: {msg.condition_summary}"
    )

    ctx.logger.info(
        f"Action required: {msg.action_required}"
    )

    ctx.logger.info(
        f"Recommended object: {msg.recommended_object}"
    )

    ctx.logger.info(
        f"Urgency: {msg.urgency}"
    )


    result = {

        "source_agent":
            "MonitoringAgent",

        "condition_summary":
            msg.condition_summary,

        "action_required":
            msg.action_required,

        "recommended_object":
            msg.recommended_object,

        "urgency":
            msg.urgency,

        "status":
            msg.status,
    }


    await process_specialist_result(
        ctx,
        msg.task_id,
        result,
    )


# ===========================================================================
# IMAGEPROCESSINGAGENT -> CAREBOT
# ===========================================================================

@agent.on_message(
    model=ImageProcessingResult
)
async def handle_image_result(
    ctx: Context,
    sender: str,
    msg: ImageProcessingResult,
):

    ctx.logger.info(
        f"Received ImageProcessingResult for task {msg.task_id}"
    )

    ctx.logger.info(
        f"Target: {msg.target_object}"
    )

    ctx.logger.info(
        f"Visible: {msg.target_visible}"
    )

    ctx.logger.info(
        f"Direction: {msg.direction}"
    )

    ctx.logger.info(
        f"Description: {msg.description}"
    )


    state = get_task_state(
        ctx,
        msg.task_id,
    )


    if not state:

        ctx.logger.warning(
            f"Received ImageProcessingResult for unknown task {msg.task_id}"
        )

        return


    # Store the authoritative Bedrock vision output.
    state["latest_image_result"] = {

        "target_object":
            msg.target_object,

        "target_visible":
            msg.target_visible,

        "direction":
            msg.direction,

        "description":
            msg.description,
    }


    save_task_state(
        ctx,
        msg.task_id,
        state,
    )


    result = {

        "source_agent":
            "ImageProcessingAgent",

        "target_object":
            msg.target_object,

        "target_visible":
            msg.target_visible,

        "direction":
            msg.direction,

        "description":
            msg.description,
    }


    await process_specialist_result(
        ctx,
        msg.task_id,
        result,
    )


# ===========================================================================
# ACTIONAGENT -> CAREBOT
# ===========================================================================

@agent.on_message(
    model=ActionResult
)
async def handle_action_result(
    ctx: Context,
    sender: str,
    msg: ActionResult,
):

    ctx.logger.info(
        f"Received ActionResult for task {msg.task_id}"
    )

    ctx.logger.info(
        f"Target: {msg.target_object}"
    )

    ctx.logger.info(
        f"Actions: {msg.actions}"
    )

    ctx.logger.info(
        f"Status: {msg.status}"
    )


    result = {

        "source_agent":
            "ActionAgent",

        "target_object":
            msg.target_object,

        "actions":
            msg.actions,

        "status":
            msg.status,
    }


    await process_specialist_result(
        ctx,
        msg.task_id,
        result,
    )


# ===========================================================================
# STARTUP
# ===========================================================================

@agent.on_event("startup")
async def startup(
    ctx: Context,
):

    ctx.logger.info(
        f"CareBot address: {agent.address}"
    )

    ctx.logger.info(
        f"HealthMonitoring digest: {monitoring_protocol.digest}"
    )

    ctx.logger.info(
        f"ImageProcessing digest: {image_protocol.digest}"
    )

    ctx.logger.info(
        f"MovementDelegation digest: {action_protocol.digest}"
    )


# ===========================================================================
# RUN
# ===========================================================================

if __name__ == "__main__":
    agent.run()