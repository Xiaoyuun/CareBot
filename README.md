## Architecture

- CareBot — hosted on Agentverse
- ActionAgent — hosted on Agentverse
- MonitoringAgent — hosted on Agentverse
- ImageProcessingAgent — runs locally and connects through Agentverse Mailbox
- ASI:One — user-facing chat interface
- AWS S3 — simulated camera image storage
- Amazon Bedrock / Nova Lite — image understanding

ASI:One
   ↓
CareBot
   ├── MonitoringAgent
   ├── ImageProcessingAgent (local/mailbox)
   │      ├── S3
   │      └── Bedrock Nova
   └── ActionAgent

## Run ImageProcessingAgent locally

1. Create a virtual environment
2. Install dependencies:

   pip install -r requirements.txt

3. Set:

   AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY

4. Run:

   python image_processing_agent/agent.py

## Agentverse Agents

- CareBot
  - Address: agent1...
  - Agentverse: <profile link>

- ActionAgent
  - Address: agent1...
  - Agentverse: <profile link>

- ImageProcessingAgent
  - Address: agent1...
  - Runs locally via Agentverse Mailbox