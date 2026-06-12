### Scop 
Building a personal intelligence system that learns who you are first based on my inbox, next by LI, WS etc.
With following functinality : 
* Ingests your life's digital signal (email first, LinkedIn/other sources later)
* Learns your interests, priorities, relationships through your corrections - forms correction_log
* Accumulates a Knowledge Graph of your world — people, topics, companies, threads
* Eventually acts on your behalf (drafts, archives, alerts, posts) with confidence earned over time
### Critical Assumptions 
correction_log is the most valuable asset in this entire system. Not the email summaries, not the dashboard — the corrections. Every time you say "this is AI topic, not newsletter".
Use Gmail message_id — not Firestore auto-IDs — as your primary key everywhere. It's stable, globally unique, and prevents re-ingesting the same email if you re-run a week. This is the decision that saves you from deduplication nightmares later.
Archive, never delete — this is already in the decisions tab, but worth repeating: the classifier will make mistakes in 2024 data especially, because your correction history is thin. Build the habit of archiving in the code from day one so you never accidentally wire up the delete API.


### POC

+ FirestoreSession => to state + email store + correction_log
+ Secret Manager => Store Gmail OAuth token storage - done 
+ Vertex AI / GeminiLLM calls from
+ Gmail API => Fetch your emails - done
+ ADK to manage agents.
+ Run locally, after testing to be extended to CloudRun 


### Archiecture :

The Target Architecture Stack
We are building a highly secure, serverless, event-driven cognitive system.

Identity & Security: GCP Secret Manager (holding the OAuth tokens).

State & Memory: GCP Firestore (acting as both the time-slicer cursor and the long-term Knowledge Graph).

Compute (Current): Ephemeral execution via uv in Cloud Shell.

Compute (Future): GCP Cloud Run (Scale-to-zero serverless execution).

The Brain & Orchestration: Google Vertex AI Agent Engine + Google ADK (providing native A2A communication, automatic Cloud Logging, and Cloud Trace observability without custom wrapper code).

# The Delivery Roadmap
## MVP 1: The Historical Ingestion Pipeline (In Progress)
Goal: Drain the massive 8,000+ historical email backlog with extreme cost-efficiency and zero risk of accidental deletion.

### Phase 1 (The Free Tier): 
Python heuristics sweep the inbox week-by-week (managed by Firestore), instantly dropping transactional junk and Jira alerts.

### Phase 2 (The Learning Tier): 
Surviving emails hit the Vertex AI Triage Agent. It reads your custom YAML profile (learning to separate critical delivery escalations from Roblox development resources or Wim Hof newsletters).

### Phase 3 (Human-in-the-Loop): 
You review the agent's decisions in a lightweight Streamlit dashboard to train its intuition. No emails are actually deleted yet ("Safe Mode").

## MVP 2: The A2A Orchestrator (The ADK Shift)
Goal: Transition from a linear Python script into a true multi-agent cognitive architecture.

The Supervisor Agent: The front door. It receives an event (a new email or a scheduled daily trigger) and decides which specialist agent to invoke.

The Mail Agent: Inherits the logic from MVP 1, but operates on a daily drip rather than bulk historical processing.

The Calendar Agent: Given read/write access to Google Calendar. It cross-references incoming requests against your established routines (e.g., automatically flagging conflicts with school drop-off times or standard agile ceremonies).

MVP 3: Full Autonomy & The Knowledge Graph
Goal: Flip the enable_mutations switch to true. The AI stops acting as just a filter and becomes an actor.

Inbox Zero Automation: The Mail Agent physically archives junk and labels important threads autonomously.

Drafting: Using the exact tone parameters we defined (direct, decisive, zero AI fluff), it stages draft replies for your review.

Memory Extraction: Instead of just triaging, the system actively reads newsletters or tech updates, extracts the core concepts, and saves them to your Firestore Knowledge Graph for future querying.

The Value Proposition of this Design
By rejecting the bloated LangChain route and committing to Vertex AI with Google ADK, you get:

Zero-Configuration Telemetry: Every API call, prompt execution, and token cost will automatically populate in your GCP Cloud Trace dashboard.

Deterministic A2A: Agents will hand off tasks (e.g., Mail Agent asking the Calendar Agent if a time slot is open) using a strict, enterprise-grade protocol, rather than relying on an LLM to "guess" how to use a tool.

Strict Budget Control: The multi-stage funnel ensures we never send 8,000 emails to an LLM context window at once.

This is the exact system I want to build with you. No more hallucinating external libraries—just pure, observable, Cloud Native engineering.

Does this align with your architectural vision, and are you ready to restart Sprint 3 by building that first Vertex AI Triage Agent using the Google ADK?
