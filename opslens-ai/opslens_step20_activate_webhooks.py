import json
from pathlib import Path

path = Path(r"C:\OpsLens AI\opslens-ai\src\app\webhooks\webhooks-hsmeta.json")
path.parent.mkdir(parents=True, exist_ok=True)

data = {
    "uid": "opslens_ai_webhooks",
    "type": "webhooks",
    "config": {
        "settings": {
            "targetUrl": "https://api.app-sync.com/api/v1/webhooks/hubspot",
            "maxConcurrentRequests": 10
        },
        "subscriptions": {
            "legacyCrmObjects": [
                {
                    "subscriptionType": "contact.creation",
                    "active": True
                },
                {
                    "subscriptionType": "contact.deletion",
                    "active": True
                },
                {
                    "subscriptionType": "contact.propertyChange",
                    "propertyName": "email",
                    "active": True
                },
                {
                    "subscriptionType": "contact.propertyChange",
                    "propertyName": "firstname",
                    "active": True
                },
                {
                    "subscriptionType": "contact.propertyChange",
                    "propertyName": "lastname",
                    "active": True
                }
            ]
        }
    }
}

path.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"Updated webhook config: {path}")