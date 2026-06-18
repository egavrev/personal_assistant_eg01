import json
from google import genai
from google.genai import types
import logging, time

logger = logging.getLogger("classifier")


class Classifier:
    def __init__(self, project_id: str, cfg: dict):
        self.cfg = cfg
        self.model = cfg["model"]
        self.prompt = cfg["classifier_prompt_template"]
        self.client = genai.Client(
            vertexai=True, project=project_id, location=cfg.get("location", "global")
        )

    def classify(self, signal: dict, body_excerpt: str, corrections_context: str = "") -> dict:
        """Returns the classification dict, or a low-confidence fallback on parse failure."""
        t0 = time.time()
        prompt = self._build_prompt(signal, body_excerpt, corrections_context)
        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,                 # triage wants consistency, not creativity
                    response_mime_type="application/json",
                ),
            )
            dt = time.time() - t0
            um = getattr(resp, "usage_metadata", None)
            logger.info("gemini ok model=%s tokens=%s latency=%.2fs subject=%r",
                self.model, um.total_token_count if um else "?", dt,
                signal.get("subject","")[:40])
            data = json.loads(resp.text)
            return self._validate(data, resp)
        except (json.JSONDecodeError, ValueError) as e:
            # Never crash a batch on one bad response — route it to human review.
            logger.warning("gemini FAIL model=%s err=%s subject=%r",
                   self.model, str(e)[:120], signal.get("subject","")[:40])
            return {
                "category": "Other", "topics": [], "sender_type": "system",
                "needs_reply": False, "confidence": 0.0,
                "model": self.model, "error": f"parse_failure: {str(e)[:100]}",
            }

    def _build_prompt(self, signal, body_excerpt, corrections_context) -> str:
        with open(self.prompt) as f:
            template = f.read()
        return template.format(
            categories="\n".join(f"- {c}" for c in self.cfg["categories"]),
            seed_interests=", ".join(self.cfg.get("seed_interests", [])),
            corrections_context=corrections_context or "(no past corrections yet)",
            sender=signal.get("sender_raw", ""),
            subject=signal.get("subject", ""),
            snippet=signal.get("snippet", ""),
            body=body_excerpt,
        )

    def _validate(self, data: dict, resp) -> dict:
        cats = self.cfg["categories"]
        if data.get("category") not in cats:
            data["category"] = "Other"
            data["confidence"] = min(float(data.get("confidence", 0.5)), 0.4)
        data["category"] = data.get("category", "Other")
        data["topics"] = data.get("topics", [])[:5]
        data["sender_type"] = data.get("sender_type", "system")
        data["needs_reply"] = bool(data.get("needs_reply", False))
        data["confidence"] = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
        data["model"] = self.model
        data["prompt_version"] = "v1"
        # token usage for cost tracking
        um = getattr(resp, "usage_metadata", None)
        data["_tokens"] = (um.total_token_count if um else 0)
        return data