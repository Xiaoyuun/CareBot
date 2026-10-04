"""
Health monitoring logic.

This module:
- performs deterministic anomaly checks
- invokes Bedrock only when a demo anomaly rule fires
- returns a structured Decision

It does NOT:
- perform Fetch.ai messaging
- perform spatial lookup
- invoke ImageProcessingAgent
- read/write S3 directly

CareBot is responsible for deciding what happens after this result.
"""

from datetime import datetime, timezone
from uuid import uuid4

import aws_io as aws


# ===========================================================================
# VALID CONTRACT VALUES
# ===========================================================================

VALID_ACTIONS = {
    "no_action",
    "notify",
    "escalate",
}

VALID_SEVERITIES = {
    "none",
    "low",
    "medium",
    "high",
}


# ===========================================================================
# HELPERS
# ===========================================================================

def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def make_no_action_decision(
    snapshot: dict,
    message: str,
) -> dict:

    return {
        "schema_version": "1.0",

        "decision_id":
            f"dec_{uuid4().hex[:12]}",

        "snapshot_id":
            snapshot["snapshot_id"],

        "patient_id":
            snapshot["patient_id"],

        "timestamp":
            utc_timestamp(),

        "action":
            "no_action",

        "severity":
            "none",

        "message":
            message,

        "observations":
            [],

        # Keep this field available to CareBot.
        "spatial_lookup_item":
            None,

        "safety": {
            "diagnosis_made": False,
            "new_medication_recommended": False,
        },
    }


# ===========================================================================
# ONE MONITORING CYCLE
# ===========================================================================

def run_cycle(
    snapshot: dict,
) -> dict:
    """
    Analyze one synthetic health snapshot.

    Flow:

        snapshot
           ↓
        deterministic anomaly gate
           ↓
        Bedrock only if necessary
           ↓
        structured Decision

    If Bedrock recommends locating an existing item, that recommendation is
    returned in `spatial_lookup_item`.

    The monitoring component does NOT perform the lookup itself.
    CareBot decides whether ImageProcessingAgent should be invoked.
    """

    # -----------------------------------------------------------------------
    # DETERMINISTIC ANOMALY RULES
    #
    # These are synthetic demo heuristics, not medical thresholds.
    # -----------------------------------------------------------------------

    scheduled_trigger = any(
        instruction.get("acknowledged") is False
        for instruction
        in snapshot.get(
            "scheduled_instructions",
            [],
        )
    )


    heart_rate_trigger = (
        snapshot["current"]["heart_rate_bpm"]
        >=
        snapshot["baseline"][
            "resting_heart_rate_bpm"
        ] + 15
    )


    temp_trigger = (
        snapshot["current"]["skin_temperature_c"]
        >=
        snapshot["baseline"][
            "skin_temperature_c"
        ] + 0.8
    )


    # -----------------------------------------------------------------------
    # NO ANOMALY
    #
    # Do not waste a Bedrock call.
    # -----------------------------------------------------------------------

    if not (
        scheduled_trigger
        or heart_rate_trigger
        or temp_trigger
    ):

        return make_no_action_decision(
            snapshot,
            "No anomaly rule triggered.",
        )


    # -----------------------------------------------------------------------
    # RECORD WHICH RULES FIRED
    # -----------------------------------------------------------------------

    triggered_rules = []


    if scheduled_trigger:

        triggered_rules.append(
            "scheduled_instruction_due_unacknowledged"
        )


    if heart_rate_trigger:

        triggered_rules.append(
            "heart_rate_above_demo_baseline"
        )


    if temp_trigger:

        triggered_rules.append(
            "skin_temperature_above_demo_baseline"
        )


    # -----------------------------------------------------------------------
    # BEDROCK REASONING
    # -----------------------------------------------------------------------

    try:

        decision = aws.invoke_bedrock(
            {
                "snapshot":
                    snapshot,

                "triggered_signals":
                    triggered_rules,

                "research_context":
                    None,
            }
        )


    except Exception:

        return make_no_action_decision(
            snapshot,
            "Bedrock invocation failed; no demo action was taken.",
        )


    # -----------------------------------------------------------------------
    # VALIDATE BEDROCK RESPONSE
    # -----------------------------------------------------------------------

    if not isinstance(
        decision,
        dict,
    ):

        return make_no_action_decision(
            snapshot,
            "Bedrock returned an invalid response.",
        )


    if decision.get(
        "action"
    ) not in VALID_ACTIONS:

        return make_no_action_decision(
            snapshot,
            "Bedrock returned an unsupported action.",
        )


    if decision.get(
        "severity"
    ) not in VALID_SEVERITIES:

        return make_no_action_decision(
            snapshot,
            "Bedrock returned an unsupported severity.",
        )


    # -----------------------------------------------------------------------
    # APPLICATION-CONTROLLED METADATA
    # -----------------------------------------------------------------------

    decision[
        "schema_version"
    ] = "1.0"


    decision[
        "decision_id"
    ] = f"dec_{uuid4().hex[:12]}"


    decision[
        "snapshot_id"
    ] = snapshot[
        "snapshot_id"
    ]


    decision[
        "patient_id"
    ] = snapshot[
        "patient_id"
    ]


    decision[
        "timestamp"
    ] = utc_timestamp()


    # -----------------------------------------------------------------------
    # IMPORTANT
    #
    # Do NOT call spatial.lookup_item() here.
    #
    # If Bedrock returned:
    #
    #     "spatial_lookup_item": "evening_medication"
    #
    # preserve it.
    #
    # CareBot will receive it as recommended_object and decide whether to
    # invoke ImageProcessingAgent.
    # -----------------------------------------------------------------------


    decision["safety"] = {
        "diagnosis_made": False,
        "new_medication_recommended": False,
    }


    return decision


# ===========================================================================
# ALERT HELPER
#
# Optional legacy functionality.
# The uAgent integration does not require this function.
# ===========================================================================

def build_alert(
    decision: dict,
) -> dict | None:

    if decision[
        "action"
    ] == "no_action":

        return None


    return {

        "schema_version":
            decision["schema_version"],

        "alert_id":
            f"alert_{uuid4().hex[:12]}",

        "decision_id":
            decision["decision_id"],

        "snapshot_id":
            decision["snapshot_id"],

        "patient_id":
            decision["patient_id"],

        "timestamp":
            decision["timestamp"],

        "severity":
            decision["severity"],

        "title":
            "Health monitoring alert",

        "message":
            decision["message"],

        "spatial_context":
            None,

        "source":
            "monitoring_service",
    }