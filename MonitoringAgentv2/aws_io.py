import json
import os
from unittest import result
import boto3


from dotenv import load_dotenv


load_dotenv()


AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")


s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)


REQUIRED_BEDROCK_FIELDS = {
   "action",
   "severity",
   "message",
   "observations",
   "spatial_lookup_item",
}
ALLOWED_ACTIONS = {"no_action", "notify", "escalate"}
ALLOWED_SEVERITIES = {"none", "low", "medium", "high"}




def _require_config() -> None:
   """Ensure all required AWS environment variables are set."""
   if not AWS_REGION:
       raise RuntimeError("Missing required environment variable: AWS_REGION")
   if not S3_BUCKET:
       raise RuntimeError("Missing required environment variable: S3_BUCKET")
   if not BEDROCK_MODEL_ID:
       raise RuntimeError("Missing required environment variable: BEDROCK_MODEL_ID")




def write(prefix: str, id_field: str, data: dict) -> str:
   """Write JSON to latest and history S3 keys."""
   _require_config()


   object_id = data.get(id_field)
   if not object_id:
       raise RuntimeError(f"Missing required field: {id_field}")


   latest_key = f"monitoring/{prefix}/latest.json"
   history_key = f"monitoring/{prefix}/history/{object_id}.json"
   body = json.dumps(data)


   try:
       for key in [latest_key, history_key]:
           s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(data))
   except Exception as e:
       raise RuntimeError(f"Failed to write to S3: {e}")
   return latest_key




def load_latest_snapshot() -> dict:
   """Load the latest health snapshot from S3."""
   _require_config()
   latest_key = "monitoring/health/latest.json"


   try:
       response = s3.get_object(Bucket=S3_BUCKET, Key=latest_key)
       data = json.loads(response["Body"].read())
   except Exception as e:
       raise RuntimeError(f"Failed to load latest snapshot from S3: {e}")
   return data




def write_health_snapshot(data: dict) -> str:
   """Write the health snapshot to S3."""
   return write("health", "snapshot_id", data)




def write_decision(data: dict) -> str:
   """Write latest and historical decisions to S3."""
   return write("decisions", "decision_id", data)




def write_alert(data: dict) -> str:
   """Write latest and historical alerts to S3."""
   return write("alerts", "alert_id", data)




def invoke_bedrock(context: dict) -> dict:
   _require_config()


   system_prompt = """
   You are the reasoning component of a prototype health-monitoring system.


   All health data is synthetic demo data.


   Safety rules:
   - Do not diagnose a disease or medical condition.
   - Do not prescribe a new medication.
   - Do not recommend changing medication dosage.
   - Direct medication reminder language is allowed only when an existing
     scheduled instruction is explicitly present in the provided context.
   - Monitoring-derived findings must use cautious suggestion-style language.
   - Do not invent observations that are not supported by the provided context.
   - Prefer no_action when the provided evidence does not justify notifying
     or escalating.


   Return ONLY a JSON object with exactly these fields:


   {
     "action": "no_action | notify | escalate",
     "severity": "none | low | medium | high",
     "message": "string",
     "observations": ["string"],
     "spatial_lookup_item": null
   }


   spatial_lookup_item may be null or a canonical item_name already present in
   the provided context.


   Do not include Markdown, code fences, commentary, IDs, timestamps, or any
   fields other than the five fields above.
   """.strip()


   try:
       response = bedrock.converse(
           modelId=BEDROCK_MODEL_ID,
           system=[{"text": system_prompt}],
           messages=[
               {
                   "role": "user",
                   "content": [
                       {
                           "text": "Analyze this monitoring context:\n"
                                   + json.dumps(context)
                       }
                   ],
               }
           ],
       )


       text = response["output"]["message"]["content"][0]["text"].strip()


   except Exception as e:
       raise RuntimeError(f"Failed to invoke Bedrock: {e}")


   if text.startswith("```"):
       lines = text.splitlines()
       text = "\n".join(lines[1:-1]).strip()


   try:
       result = json.loads(text)
   except Exception as e:
       raise RuntimeError(f"Failed to parse Bedrock response: {e}")


   spatial_item = (
       result.get("spatial_lookup_item")
       if isinstance(result, dict)
       else None
   )


   if (
       not isinstance(result, dict)
       or set(result) != REQUIRED_BEDROCK_FIELDS
       or result.get("action") not in ALLOWED_ACTIONS
       or result.get("severity") not in ALLOWED_SEVERITIES
       or not isinstance(result.get("message"), str)
       or not isinstance(result.get("observations"), list)
       or not all(
           isinstance(x, str)
           for x in result.get("observations", [])
       )
       or (spatial_item is not None and not isinstance(spatial_item, str))
   ):
       raise RuntimeError(
           "Bedrock response does not match required contract"
       )


   return result
