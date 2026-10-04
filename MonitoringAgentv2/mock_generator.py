"""
Generate one deterministic synthetic health snapshot on demand.


Usage:
   python mock_generator.py normal
   python mock_generator.py developing_illness
   python mock_generator.py missed_medication


Each invocation represents a controlled demo event and writes exactly one
snapshot using aws_io.write_health_snapshot().


This file does NOT detect anomalies, call Bedrock, create decisions or alerts,
or perform spatial lookup. All health values are fictional demo data.
"""


import argparse
from datetime import datetime, timedelta, timezone


from aws_io import write_health_snapshot




PATIENT_ID = "patient_demo_001"


BASELINE = {
   "resting_heart_rate_bpm": 70,
   "skin_temperature_c": 36.6,
   "typical_daily_steps": 7000,
   "typical_sleep_hours": 7.5,
}




def format_time(dt: datetime) -> str:
   """Return a UTC timestamp in the contracted format."""
   return dt.strftime("%Y-%m-%dT%H:%M:%SZ")




def make_snapshot(scenario: str) -> dict:
   """Create one deterministic snapshot for the requested demo scenario."""
   now = datetime.now(timezone.utc)
   timestamp = format_time(now)
   snapshot_id = f"snap_{now.strftime('%Y%m%dT%H%M%SZ')}"


   if scenario == "normal":
       current = {
           "heart_rate_bpm": 72,
           "skin_temperature_c": 36.7,
           "steps_today": 5200,
           "sleep_hours_last_night": 7.4,
       }
       recent_samples = [
           {
               "timestamp": format_time(now - timedelta(seconds=20)),
               "heart_rate_bpm": 70,
               "skin_temperature_c": 36.6,
           },
           {
               "timestamp": format_time(now - timedelta(seconds=10)),
               "heart_rate_bpm": 71,
               "skin_temperature_c": 36.6,
           },
           {
               "timestamp": timestamp,
               "heart_rate_bpm": 72,
               "skin_temperature_c": 36.7,
           },
       ]
       scheduled_instructions = []


   elif scenario == "developing_illness":
       current = {
           "heart_rate_bpm": 96,
           "skin_temperature_c": 37.8,
           "steps_today": 1830,
           "sleep_hours_last_night": 5.9,
       }
       recent_samples = [
           {
               "timestamp": format_time(now - timedelta(seconds=20)),
               "heart_rate_bpm": 74,
               "skin_temperature_c": 36.7,
           },
           {
               "timestamp": format_time(now - timedelta(seconds=10)),
               "heart_rate_bpm": 84,
               "skin_temperature_c": 37.2,
           },
           {
               "timestamp": timestamp,
               "heart_rate_bpm": 96,
               "skin_temperature_c": 37.8,
           },
       ]
       scheduled_instructions = []


   else:  # missed_medication
       current = {
           "heart_rate_bpm": 71,
           "skin_temperature_c": 36.6,
           "steps_today": 4100,
           "sleep_hours_last_night": 7.2,
       }
       recent_samples = [
           {
               "timestamp": format_time(now - timedelta(seconds=20)),
               "heart_rate_bpm": 70,
               "skin_temperature_c": 36.6,
           },
           {
               "timestamp": format_time(now - timedelta(seconds=10)),
               "heart_rate_bpm": 71,
               "skin_temperature_c": 36.6,
           },
           {
               "timestamp": timestamp,
               "heart_rate_bpm": 71,
               "skin_temperature_c": 36.6,
           },
       ]
       scheduled_instructions = [
           {
               "instruction_id": "med_evening_001",
               "kind": "medication_reminder",
               "item_name": "evening_medication",
               "scheduled_at": format_time(now - timedelta(minutes=20)),
               "acknowledged": False,
           }
       ]


   return {
       "schema_version": "1.0",
       "snapshot_id": snapshot_id,
       "patient_id": PATIENT_ID,
       "timestamp": timestamp,
       "scenario": scenario,
       "current": current,
       "baseline": BASELINE,
       "recent_samples": recent_samples,
       "scheduled_instructions": scheduled_instructions,
   }




def main() -> None:
   parser = argparse.ArgumentParser(
       description="Write one synthetic health event to S3."
   )
   parser.add_argument(
       "scenario",
       choices=["normal", "developing_illness", "missed_medication"],
   )
   args = parser.parse_args()


   snapshot = make_snapshot(args.scenario)


   try:
       key = write_health_snapshot(snapshot)
       print(f"Wrote {args.scenario} snapshot to {key}")
       print(f"Snapshot ID: {snapshot['snapshot_id']}")
   except RuntimeError as exc:
       print(f"Failed to write snapshot: {exc}")




if __name__ == "__main__":
   main()
