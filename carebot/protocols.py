"""
CareBot protocols and orchestration helpers.

CareBot is the central reasoning/orchestration agent.

Every specialist result returns to CareBot.
CareBot then calls ASI:One again to decide what happens next.

Workflow:

User
  -> CareBot
  -> ASI:One reasoning
  -> specialist agent
  -> CareBot
  -> ASI:One reasoning
  -> next specialist / clarification / finish
"""

import json
import os

from datetime import datetime, timezone
from uuid import uuid4

from openai import OpenAI

from uagents import Context, Field, Model, Protocol

from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)


# ===========================================================================
# AGENT ADDRESSES
# ===========================================================================

MONITORING_AGENT_ADDRESS = (
    "agent1qtmwehcd87zm5jzjdup0lecrgzvxlw8ceds5h0vzc7h0mwwd77s5z8xsxyn"
)

IMAGE_PROCESSING_AGENT_ADDRESS = (
    "agent1qv3d369cq582fanlwzwxuehg8q97r0hwx4c6nkzdvpm32cnrw4u4w8j272c"
)

ACTION_AGENT_ADDRESS = (
    "agent1qdl0gs76fzy4ejuct7ax2kzc3z7jszmd056nf8zwvk46cgrud07mv9we4ev"
)


# ===========================================================================
# STATIC S3 CAMERA IMAGE
#
# You are currently uploading one fixed image to S3.
# CareBot will send this same S3 key to ImageProcessingAgent each time.
# ===========================================================================

STATIC_IMAGE_KEY = os.getenv(
    "CAREBOT_IMAGE_KEY",
    "camera/kitchen.jpg",
)


# ===========================================================================
# ASI:ONE CLIENT
#
# Set ASI_ONE_API_KEY in Agentverse / environment variables.
# Do not commit the real API key to GitHub.
# ===========================================================================

ASI_ONE_API_KEY = os.getenv(
    "ASI_ONE_API_KEY"
)

if not ASI_ONE_API_KEY:
    raise RuntimeError(
        "ASI_ONE_API_KEY environment variable is not set"
    )


client = OpenAI(
    base_url="https://api.asi1.ai/v1",
    api_key=ASI_ONE_API_KEY,
)


# ===========================================================================
# PERSISTENT TASK STATE
# ===========================================================================

def get_task_state(
    ctx: Context,
    task_id: str,
) -> dict | None:

    return ctx.storage.get(
        f"task:{task_id}"
    )


def save_task_state(
    ctx: Context,
    task_id: str,
    state: dict,
):

    ctx.storage.set(
        f"task:{task_id}",
        state,
    )


# ===========================================================================
# CAREBOT SYSTEM PROMPT
# ===========================================================================

CAREBOT_SYSTEM_PROMPT = """
You are CareBot, the coordinator of a multi-agent healthcare assistance
system.

You communicate naturally with the user while coordinating specialized
agents.

You decide what should happen NEXT based on:

1. The user's original request.
2. Results returned by specialist agents.
3. The steps that have already happened.

AVAILABLE SPECIALISTS

MonitoringAgent
- Handles health-state information.
- Use for heart rate, pulse, BPM, SpO2, glucose, temperature, symptoms,
  dizziness, breathing information, and similar health context.
- May recommend an assistive object.

ImageProcessingAgent
- Looks for a requested physical object in a static camera image.
- Returns:

    target_visible
    direction
    description

- direction is:
    left
    center
    right
    unknown

- description contains useful visual information about what the vision model
  observed and where the object appears.

ActionAgent
- Generates simulated robot movement/actions.
- Use only AFTER ImageProcessingAgent has found the requested object.
- Receives the target object, direction, and scene description.

You may also:
- ask the user for clarification
- finish the workflow

IMPORTANT:

Do NOT blindly follow a fixed pipeline.

After EVERY specialist result, reevaluate the current state and decide what
should happen next.

Examples:

If health information requires evaluation:
    MonitoringAgent may be appropriate.

If MonitoringAgent recommends retrieving an object:
    ImageProcessingAgent may be appropriate.

If ImageProcessingAgent says target_visible=false:
    DO NOT invoke ActionAgent.

If ImageProcessingAgent says target_visible=true:
    ActionAgent may be appropriate.

If ActionAgent successfully creates an action plan:
    the workflow will usually be complete.

Never invent specialist results.

The structured specialist outputs are authoritative.

Return ONLY valid JSON:

{
    "next_step":
        "monitoring"
        | "image_processing"
        | "action"
        | "clarification"
        | "finish",

    "target_object": string | null,

    "health_context": string | null,

    "user_message": string,

    "task_complete": boolean
}

"user_message" is displayed directly to the user.

Use it to briefly explain:
- what was learned
- what CareBot is doing next

For example:

"The vision system found your EpiPen on the right side of the scene.
I'll ask the movement agent to determine how the robot should approach it."

Do not expose hidden chain-of-thought or private reasoning.

Give only concise progress explanations.

Do not mention JSON, model schemas, protocols, or implementation details
unless the user asks about them.
"""


# ===========================================================================
# MONITORING MODELS
#
# Must exactly match MonitoringAgent.
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
# IMAGE PROCESSING MODELS
#
# These match the REAL Bedrock inspect_scene() output.
# ===========================================================================

class ImageProcessingRequest(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    target_object: str = Field(
        description="Object that should be located in the scene"
    )

    raw_request: str = Field(
        description="Original natural-language request from the user"
    )

    image_reference: str = Field(
        description="S3 object key for the image to analyze"
    )


class ImageProcessingResult(Model):

    task_id: str = Field(
        description="Unique CareBot workflow identifier"
    )

    target_object: str = Field(
        description="Object searched for by the vision agent"
    )

    target_visible: bool = Field(
        description="Whether the requested target was found"
    )

    direction: str = Field(
        description="Target direction: left, center, right, or unknown"
    )

    description: str = Field(
        description="Short description of what the vision model observed"
    )


# ===========================================================================
# ACTION MODELS
#
# ActionAgent now receives the REAL vision result rather than mock distance
# fields.
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
# PROTOCOLS
# ===========================================================================

chat_protocol = Protocol(
    spec=chat_protocol_spec
)

monitoring_protocol = Protocol(
    name="HealthMonitoring",
    version="1.0",
)

image_protocol = Protocol(
    name="ImageProcessing",
    version="1.0",
)

action_protocol = Protocol(
    name="MovementDelegation",
    version="1.0",
)


# ===========================================================================
# CHAT HELPERS
# ===========================================================================

def create_text_message(
    text: str,
) -> ChatMessage:

    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(
                type="text",
                text=text,
            )
        ],
    )


def extract_chat_text(
    msg: ChatMessage,
) -> str:

    chunks = []

    for item in msg.content:

        if isinstance(item, TextContent):
            chunks.append(item.text)

    return "".join(chunks).strip()


async def send_user_update(
    ctx: Context,
    task_id: str,
    text: str,
):

    state = get_task_state(
        ctx,
        task_id,
    )

    if not state:

        ctx.logger.warning(
            f"No task state found for {task_id}"
        )

        return


    chat_sender = state.get(
        "chat_sender"
    )


    if not chat_sender:

        ctx.logger.warning(
            f"No chat sender stored for {task_id}"
        )

        return


    await ctx.send(
        chat_sender,
        create_text_message(text),
    )


# ===========================================================================
# ASI:ONE RESPONSE PARSING
# ===========================================================================

def parse_json_response(
    content: str,
) -> dict:

    content = content.strip()


    if content.startswith("```"):

        content = content.replace(
            "```json",
            "",
            1,
        )

        content = content.replace(
            "```",
            "",
        )

        content = content.strip()


    return json.loads(content)


# ===========================================================================
# CAREBOT REASONING
# ===========================================================================

def reason_about_state(
    ctx: Context,
    task_id: str,
    latest_result: dict | None = None,
) -> dict:

    state = get_task_state(
        ctx,
        task_id,
    )


    if state is None:

        raise RuntimeError(
            f"No state exists for task {task_id}"
        )


    reasoning_input = {

        "task_id":
            task_id,

        "original_user_request":
            state["original_request"],

        "previous_events":
            state["events"],

        "latest_specialist_result":
            latest_result,
    }


    response = client.chat.completions.create(

        model="asi1",

        messages=[

            {
                "role": "system",
                "content": CAREBOT_SYSTEM_PROMPT,
            },

            {
                "role": "user",

                "content": json.dumps(
                    reasoning_input,
                    indent=2,
                ),
            },
        ],

        max_tokens=600,
    )


    content = response.choices[0].message.content


    if content is None:

        raise RuntimeError(
            "ASI:One returned no content."
        )


    return parse_json_response(
        content
    )


# ===========================================================================
# EXECUTE CAREBOT DECISION
# ===========================================================================

async def execute_decision(
    ctx: Context,
    task_id: str,
    decision: dict,
):

    state = get_task_state(
        ctx,
        task_id,
    )


    if not state:

        ctx.logger.warning(
            f"No state for task {task_id}"
        )

        return


    next_step = decision.get(
        "next_step",
        "clarification",
    )


    target_object = decision.get(
        "target_object"
    )


    health_context = decision.get(
        "health_context"
    )


    ctx.logger.info(
        f"CareBot next step for {task_id}: {next_step}"
    )


    # =======================================================================
    # MONITORING
    # =======================================================================

    if next_step == "monitoring":

        request = MonitoringRequest(

            task_id=task_id,

            raw_request=state[
                "original_request"
            ],

            health_context=(
                health_context
                or state["original_request"]
            ),
        )


        await ctx.send(
            MONITORING_AGENT_ADDRESS,
            request,
        )


        state["events"].append({
            "event":
                "MonitoringAgent invoked"
        })


        save_task_state(
            ctx,
            task_id,
            state,
        )


        ctx.logger.info(
            f"MonitoringRequest sent for {task_id}"
        )


    # =======================================================================
    # IMAGE PROCESSING
    # =======================================================================

    elif next_step == "image_processing":

        if not target_object:

            await send_user_update(
                ctx,
                task_id,
                "I need to know which object I should look for.",
            )

            return


        request = ImageProcessingRequest(

            task_id=task_id,

            target_object=target_object,

            raw_request=state[
                "original_request"
            ],

            # Static S3 image.
            image_reference=STATIC_IMAGE_KEY,
        )


        await ctx.send(
            IMAGE_PROCESSING_AGENT_ADDRESS,
            request,
        )


        state["events"].append({

            "event":
                "ImageProcessingAgent invoked",

            "target_object":
                target_object,

            "image_reference":
                STATIC_IMAGE_KEY,
        })


        save_task_state(
            ctx,
            task_id,
            state,
        )


        ctx.logger.info(
            f"ImageProcessingRequest sent for {task_id}"
        )


    # =======================================================================
    # ACTION
    # =======================================================================

    elif next_step == "action":

        vision_result = state.get(
            "latest_image_result"
        )


        if not vision_result:

            await send_user_update(
                ctx,
                task_id,
                "I don't have a vision result yet, so I can't plan movement.",
            )

            return


        if not vision_result[
            "target_visible"
        ]:

            await send_user_update(
                ctx,
                task_id,
                "The object hasn't been located, so I can't plan movement toward it.",
            )

            return


        request = MovementTask(

            task_id=task_id,

            target_object=vision_result[
                "target_object"
            ],

            direction=vision_result[
                "direction"
            ],

            scene_description=vision_result[
                "description"
            ],

            pick_up=True,
        )


        await ctx.send(
            ACTION_AGENT_ADDRESS,
            request,
        )


        state["events"].append({

            "event":
                "ActionAgent invoked",

            "target_object":
                vision_result["target_object"],

            "direction":
                vision_result["direction"],
        })


        save_task_state(
            ctx,
            task_id,
            state,
        )


        ctx.logger.info(
            f"MovementTask sent for {task_id}"
        )


    # =======================================================================
    # CLARIFICATION
    # =======================================================================

    elif next_step == "clarification":

        state["events"].append({
            "event":
                "Waiting for user clarification"
        })


        save_task_state(
            ctx,
            task_id,
            state,
        )


        ctx.logger.info(
            f"Waiting for clarification for {task_id}"
        )


    # =======================================================================
    # FINISH
    # =======================================================================

    elif next_step == "finish":

        state["complete"] = True


        state["events"].append({
            "event":
                "Workflow completed"
        })


        save_task_state(
            ctx,
            task_id,
            state,
        )


        ctx.logger.info(
            f"Task {task_id} completed."
        )


    else:

        ctx.logger.warning(
            f"Unknown next step: {next_step}"
        )


# ===========================================================================
# ASI:ONE -> CAREBOT
# ===========================================================================

@chat_protocol.on_message(ChatMessage)
async def handle_chat_message(
    ctx: Context,
    sender: str,
    msg: ChatMessage,
):

    await ctx.send(

        sender,

        ChatAcknowledgement(
            timestamp=datetime.now(
                timezone.utc
            ),
            acknowledged_msg_id=msg.msg_id,
        ),
    )


    text = extract_chat_text(
        msg
    )


    if not text:
        return


    ctx.logger.info(
        f"CareBot received: {text}"
    )


    task_id = str(
        uuid4()
    )


    initial_state = {

        "original_request":
            text,

        "chat_sender":
            sender,

        "events":
            [],

        "latest_image_result":
            None,

        "complete":
            False,
    }


    save_task_state(
        ctx,
        task_id,
        initial_state,
    )


    ctx.logger.info(
        f"Created persistent task state for {task_id}"
    )


    try:

        decision = reason_about_state(

            ctx=ctx,

            task_id=task_id,

            latest_result=None,
        )


        ctx.logger.info(
            f"Initial CareBot decision: {decision}"
        )


    except Exception as exc:

        ctx.logger.exception(
            f"ASI:One reasoning failed: {exc}"
        )


        await send_user_update(
            ctx,
            task_id,
            "I had trouble interpreting that request. Please try again.",
        )


        return


    user_message = decision.get(
        "user_message",
        "I'll take a look at that.",
    )


    await send_user_update(
        ctx,
        task_id,
        user_message,
    )


    try:

        await execute_decision(
            ctx,
            task_id,
            decision,
        )


    except Exception as exc:

        ctx.logger.exception(
            f"Unable to execute CareBot decision: {exc}"
        )


        await send_user_update(
            ctx,
            task_id,
            "I understood the request, but I couldn't start the next step.",
        )


# ===========================================================================
# CHAT ACK
# ===========================================================================

@chat_protocol.on_message(
    ChatAcknowledgement
)
async def handle_chat_ack(
    ctx: Context,
    sender: str,
    msg: ChatAcknowledgement,
):

    pass


# ===========================================================================
# SHARED PROTOCOL MANIFESTS
# ===========================================================================

@monitoring_protocol.on_message(
    model=MonitoringRequest,
    replies=MonitoringResult,
)
async def handle_unexpected_monitoring_request(
    ctx: Context,
    sender: str,
    msg: MonitoringRequest,
):

    ctx.logger.warning(
        "CareBot unexpectedly received MonitoringRequest."
    )


@image_protocol.on_message(
    model=ImageProcessingRequest,
    replies=ImageProcessingResult,
)
async def handle_unexpected_image_request(
    ctx: Context,
    sender: str,
    msg: ImageProcessingRequest,
):

    ctx.logger.warning(
        "CareBot unexpectedly received ImageProcessingRequest."
    )


@action_protocol.on_message(
    model=MovementTask,
    replies=ActionResult,
)
async def handle_unexpected_movement_task(
    ctx: Context,
    sender: str,
    msg: MovementTask,
):

    ctx.logger.warning(
        "CareBot unexpectedly received MovementTask."
    )