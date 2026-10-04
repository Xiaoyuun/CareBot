"""
ImageProcessingAgent.

Uses:
    S3 -> image bytes
    Amazon Bedrock Nova Lite -> vision analysis

The existing inspect_scene(target, image_key) function remains the core
implementation.
"""

import asyncio
import boto3
import json

from uagents import Context, Field, Model, Protocol


# ===========================================================================
# AWS
# ===========================================================================

bedrock = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1"
)


s3 = boto3.client(
    "s3",
    region_name="us-east-1"
)


BUCKET_NAME = "carebot-camera-mhacks"


# ===========================================================================
# MESSAGE MODELS
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
# REAL AWS BEDROCK IMPLEMENTATION
# ===========================================================================

def inspect_scene(
    target,
    image_key,
):
    """
    Look at an image and determine where the target object is.

    Example:
        inspect_scene(
            "water bottle",
            "camera/five_bottles.jpg"
        )
    """

    # -----------------------------------------------------------------------
    # 1. Get the static image from S3
    # -----------------------------------------------------------------------

    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=image_key
    )


    image_bytes = response[
        "Body"
    ].read()


    # -----------------------------------------------------------------------
    # 2. Vision prompt
    # -----------------------------------------------------------------------

    prompt = f"""
    You are the vision system for an assistive robot.

    The robot is searching for: {target}

    Analyze the provided image.

    Use the image itself as the coordinate frame:
    - left = left third of the image
    - center = middle third of the image
    - right = right third of the image

    Only describe the requested target.
    If multiple matching objects are visible, describe the most prominent one.

    Return ONLY JSON in this format:

    {{
        "target_visible": true or false,
        "direction": "left" | "center" | "right" | "unknown",
        "description": "brief description of the target and where it appears in the image"
    }}
    """



    # -----------------------------------------------------------------------
    # 3. Send image + prompt to Nova Lite through Bedrock
    # -----------------------------------------------------------------------

    response = bedrock.converse(

        modelId="amazon.nova-lite-v1:0",

        messages=[
            {
                "role": "user",

                "content": [

                    {
                        "image": {

                            "format":
                                "jpeg",

                            "source": {

                                "bytes":
                                    image_bytes
                            }
                        }
                    },

                    {
                        "text":
                            prompt
                    }
                ]
            }
        ]
    )


    # -----------------------------------------------------------------------
    # 4. Read response
    # -----------------------------------------------------------------------

    response_text = response[
        "output"
    ][
        "message"
    ][
        "content"
    ][0][
        "text"
    ]


    # -----------------------------------------------------------------------
    # 5. Convert JSON to dictionary
    # -----------------------------------------------------------------------

    result = json.loads(
        response_text
    )


    return result


# ===========================================================================
# PROTOCOL
# ===========================================================================

image_protocol = Protocol(
    name="ImageProcessing",
    version="1.0",
)


# ===========================================================================
# CAREBOT -> IMAGEPROCESSINGAGENT
# ===========================================================================

@image_protocol.on_message(
    model=ImageProcessingRequest,
    replies=ImageProcessingResult,
)
async def handle_image_processing_request(
    ctx: Context,
    sender: str,
    msg: ImageProcessingRequest,
):

    ctx.logger.info(
        f"Received image task {msg.task_id}"
    )

    ctx.logger.info(
        f"Searching for: {msg.target_object}"
    )

    ctx.logger.info(
        f"S3 image key: {msg.image_reference}"
    )


    try:

        result = await asyncio.to_thread(
            inspect_scene,
            msg.target_object,
            msg.image_reference,
        )


        ctx.logger.info(
            f"Bedrock result: {result}"
        )


    except Exception as exc:

        ctx.logger.exception(
            f"Image processing failed: {exc}"
        )


        await ctx.send(

            sender,

            ImageProcessingResult(

                task_id=
                    msg.task_id,

                target_object=
                    msg.target_object,

                target_visible=
                    False,

                direction=
                    "unknown",

                description=
                    "The image could not be analyzed.",
            ),
        )


        return


    await ctx.send(

        sender,

        ImageProcessingResult(

            task_id=
                msg.task_id,

            target_object=
                msg.target_object,

            target_visible=
                result["target_visible"],

            direction=
                result["direction"],

            description=
                result["description"],
        ),
    )


    ctx.logger.info(
        f"ImageProcessingResult returned for {msg.task_id}"
    )