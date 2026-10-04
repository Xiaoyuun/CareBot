"""
ActionAgent protocol.

ActionAgent receives vision information from CareBot:

    direction
    scene_description

It converts that information into recommended robot movement steps.

CareBot decides whether ActionAgent should be invoked.
"""

from uagents import Context, Field, Model, Protocol


# ===========================================================================
# MESSAGE MODELS
#
# MUST exactly match CareBot.
# ===========================================================================

class MovementTask(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    target_object: str = Field(
        description="Object the robot should move toward"
    )

    direction: str = Field(
        description="Direction of target: left, center, right, or unknown"
    )

    scene_description: str = Field(
        description="Vision model description of the target and scene"
    )

    pick_up: bool = Field(
        description="Whether the object should be picked up"
    )


class ActionResult(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    target_object: str = Field(
        description="Object targeted by the movement plan"
    )

    actions: list[str] = Field(
        description="Ordered simulated movement commands"
    )

    status: str = Field(
        description="Action-planning status"
    )


# ===========================================================================
# ACTION PLANNER
# ===========================================================================

def generate_action_plan(
    direction: str,
    scene_description: str,
    pick_up: bool,
) -> list[str]:
    """
    Convert the vision result into recommended robot movement steps.

    For the current MVP, the planner uses the target direction to determine
    how the robot should orient itself, then recommends moving forward.

    scene_description is preserved so it can be used later for smarter
    planning.

    No movement is actually executed here.
    """

    actions = []

    direction = direction.lower()


    # -----------------------------------------------------------------------
    # 1. Orient toward the target
    # -----------------------------------------------------------------------

    if direction == "left":

        actions.append(
            "TURN_LEFT"
        )


    elif direction == "right":

        actions.append(
            "TURN_RIGHT"
        )


    elif direction == "center":

        # Target is already roughly in front of the robot.
        pass


    else:

        # Vision did not provide a usable direction.
        actions.append(
            "SEARCH_FOR_TARGET"
        )

        return actions


    # -----------------------------------------------------------------------
    # 2. Move toward the target
    #
    # The current vision result does not include exact distance.
    # -----------------------------------------------------------------------

    actions.append(
        "MOVE_FORWARD"
    )


    # -----------------------------------------------------------------------
    # 3. Pick up target
    # -----------------------------------------------------------------------

    if pick_up:

        actions.append(
            "PICK_UP"
        )


    return actions


# ===========================================================================
# PROTOCOL
# ===========================================================================

action_protocol = Protocol(
    name="MovementDelegation",
    version="1.0",
)


# ===========================================================================
# CAREBOT -> ACTIONAGENT
# ===========================================================================

@action_protocol.on_message(
    model=MovementTask,
    replies=ActionResult,
)
async def handle_movement_task(
    ctx: Context,
    sender: str,
    msg: MovementTask,
):

    ctx.logger.info(
        f"Received MovementTask for task {msg.task_id}"
    )

    ctx.logger.info(
        f"Sender: {sender}"
    )

    ctx.logger.info(
        f"Target: {msg.target_object}"
    )

    ctx.logger.info(
        f"Direction: {msg.direction}"
    )

    ctx.logger.info(
        f"Scene description: {msg.scene_description}"
    )

    ctx.logger.info(
        f"Pick up requested: {msg.pick_up}"
    )


    actions = generate_action_plan(
        direction=msg.direction,
        scene_description=msg.scene_description,
        pick_up=msg.pick_up,
    )


    ctx.logger.info(
        f"Recommended action plan: {actions}"
    )


    await ctx.send(
        sender,

        ActionResult(
            task_id=msg.task_id,
            target_object=msg.target_object,
            actions=actions,
            status="completed_mock",
        ),
    )


    ctx.logger.info(
        f"ActionResult sent to CareBot for task {msg.task_id}"
    )