# CareBot

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)

CareBot is a Fetch.ai uAgents multi-agent prototype for assistive object
finding and simulated robot action planning. A user chats with CareBot through
ASI:One using the Agent Chat Protocol (ACP). CareBot uses ASI:One for
orchestration reasoning and delegates work to specialist uAgents.

## Agent directory

| Agent | Agentverse address | Role |
|---|---|---|
| CareBot | [`agent1qvger34h43pwnv8dfvk3k20j859zues825f3mwgjceau64vslccl2qjtzht`](https://agentverse.ai/agents/details/agent1qvger34h43pwnv8dfvk3k20j859zues825f3mwgjceau64vslccl2qjtzht/profile) | ACP chat interface and workflow coordinator |
| MonitoringAgent | `agent1qtmwehcd87zm5jzjdup0lecrgzvxlw8ceds5h0vzc7h0mwwd77s5z8xsxyn` | Evaluates the latest synthetic health snapshot |
| ImageProcessingAgent | `agent1qv3d369cq582fanlwzwxuehg8q97r0hwx4c6nkzdvpm32cnrw4u4w8j272c` | Analyzes the configured S3 image using Bedrock Nova Lite |
| ActionAgent | `agent1qdl0gs76fzy4ejuct7ax2kzc3z7jszmd056nf8zwvk46cgrud07mv9we4ev` | Generates a simulated movement plan |

The team has tested the Agentverse deployment and ASI:One discovery flow
successfully.

## Demo video

Submission requirement: include a 3–5 minute video demonstrating the agents
and the primary workflow. Add the published video link here before submitting.

## Fetch.ai, Agentverse, and ASI:One

- Agents are implemented with Fetch.ai's `uagents` framework.
- CareBot includes the Fetch.ai ACP chat protocol from
  `uagents_core.contrib.protocols.chat` and publishes its protocol manifest.
- Agentverse is the hosting and discovery layer for published agents.
- CareBot calls the ASI:One API for its orchestration decisions.

## Architecture

```text
User in ASI:One (ACP chat)
            |
         CareBot
        /   |    \
 Monitoring Image  Action
    Agent  Processing Agent
       |     |          |
       +-- S3/Bedrock    +-- simulated action plan
```

CareBot is the coordinator. It reasons about the request and specialist
results, then decides whether to call MonitoringAgent, ImageProcessingAgent,
ActionAgent, ask for clarification, or finish. Agent addresses are configured
in `carebot/protocols.py`.

### Specialist behavior and current limits

- **ImageProcessingAgent** analyzes a configured, static S3 image
  (`CAREBOT_IMAGE_KEY`, default `camera/kitchen.jpg`) with Amazon Bedrock Nova
  Lite. It reports whether the target is visible, its approximate left/center/
  right position, and a description. Because the prototype has no physical
  robot hardware, the static S3 image stands in for a camera frame.
- **ActionAgent** converts the vision direction into an ordered simulated
  plan, such as `TURN_RIGHT`, `MOVE_FORWARD`, and `PICK_UP`. It does not control
  physical hardware.
- **MonitoringAgent** reads the latest synthetic health snapshot from S3 and
  applies demo rules before optionally calling Bedrock. Although CareBot passes
  the original request and health context to it, the current monitoring logic
  bases its assessment on the stored snapshot, not the free-form symptom text.
  It is a prototype, not a medical diagnostic system.
- **ImageProcessingAgent and MonitoringAgent** run locally because they need
  AWS access, and connect to CareBot through Agentverse Mailbox. Keep both
  processes running on an AWS-configured machine while using their workflows.
- **CareBot** and **ActionAgent** can run locally or be deployed to Agentverse.
  The team has tested CareBot deployed through Agentverse and discovered in
  ASI:One. If running CareBot locally, configure its ASI:One API key and make
  sure the specialist addresses in `carebot/protocols.py` point to reachable
  agents.

The current prototype analyzes one image and returns a plan. Integrating a
physical camera and robot to support the continuous
`SEE → REASON → ACT → SEE AGAIN` loop is future work.

## Setup

Use Python 3.10 or newer, create and activate a virtual environment, then
install the repository dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dependency file includes the Fetch.ai `uagents` and `uagents-core`
packages, the OpenAI-compatible ASI:One client, `python-dotenv`, and the AWS
SDK packages used by this project.

### Local and hosted configuration

| Agent | Local setup | Hosted setup |
|---|---|---|
| CareBot | Run `python carebot/agent.py`; set `ASI_ONE_API_KEY` and configure reachable specialist addresses. | Deploy on Agentverse and configure `ASI_ONE_API_KEY` in the deployment's secrets/environment. |
| ActionAgent | Run `python actionAgent/agent.py`. | Deploy on Agentverse. |
| ImageProcessingAgent | Run `python ImageProcessingAgent/agent.py` on a machine with AWS access; set `IMAGE_AGENT_SEED`. Keep it running for requests. | In this prototype it runs locally via Agentverse Mailbox, not as an AWS-dependent hosted agent. |
| MonitoringAgent | Run `python MonitoringAgentv2/agent.py` on a machine with AWS access; set `MONITORING_AGENT_SEED`. Keep it running for requests. | In this prototype it runs locally via Agentverse Mailbox, not as an AWS-dependent hosted agent. |

Do not commit API keys, AWS credentials, or agent seeds. Set secrets through
your local process environment (the local AWS-dependent agents also load an
ignored `.env` file) or the hosted platform's secret configuration. Agent
addresses are public identifiers, not credentials.

### External resources

- [Fetch.ai Agentverse](https://agentverse.ai/) — agent hosting, registration,
  and discovery.
- [ASI:One](https://asi1.ai/) — user-facing agent discovery and conversation.
- [Amazon S3](https://aws.amazon.com/s3/) — image and synthetic monitoring
  snapshot storage.
- [Amazon Bedrock](https://aws.amazon.com/bedrock/) — Nova Lite image analysis
  and monitoring reasoning.

Required configuration:

- `ASI_ONE_API_KEY` — used by CareBot to call the ASI:One API.
- `IMAGE_AGENT_SEED` — required when running ImageProcessingAgent locally.
- `MONITORING_AGENT_SEED` — required when running MonitoringAgent locally.
- AWS credentials — available through the standard Boto3 credential chain.
- `AWS_REGION`, `S3_BUCKET`, and `BEDROCK_MODEL_ID` — used by the monitoring
  workflow.
- `CAREBOT_IMAGE_KEY` — optional S3 image key; defaults to
  `camera/kitchen.jpg`.

ImageProcessingAgent currently uses the `carebot-camera-mhacks` S3 bucket and
`us-east-1` region in its source. Ensure the selected image exists there and
that the AWS identity can read it. For monitoring, write one of the supported
synthetic snapshots to S3 before testing a monitoring request; see
`MonitoringAgentv2/mock_generator.py`.

Run a local agent from the repository root (each command starts one agent;
start only the agents needed for the chosen deployment, and keep local
mailbox agents running):

```bash
python carebot/agent.py
python actionAgent/agent.py
python ImageProcessingAgent/agent.py
python MonitoringAgentv2/agent.py
```

For multi-agent use, make sure CareBot's configured agent addresses point to
the active specialist agents. The local AWS-dependent agents require their
seeds and AWS configuration before startup.