# Marketplace Install Validation

## Current routing split

- Marketplace-origin installs: `/oauth-callback` redirects to the exact HubSpot-provided `returnUrl`.
- External app-sync installs: `/oauth-callback` redirects to `https://apps.app-sync.com/opslens/install/complete/`.

## Marketplace-origin validation

- Run this flow from the HubSpot App Listing Preview so HubSpot supplies the real `returnUrl`.
- Do not manually invent a HubSpot destination such as `https://app.hubspot.com/installed-apps/{portalId}`.
- The backend treats the HubSpot `returnUrl` as an opaque value and preserves it exactly on the marketplace branch.

Backend note:
A 404 on a manually invented path such as `/installed-apps/{portalId}` is not a redirect bug. It means the test used an invalid HubSpot URL that HubSpot never provided to the backend.

### Post-deploy validation steps

1. Open the OpsLens HubSpot App Listing Preview in HubSpot.
2. Start the install from that preview flow and complete the OAuth/install steps in the browser.
3. Confirm the browser returns to the HubSpot destination supplied by HubSpot, not to `https://api.app-sync.com/docs` and not to the external app-sync completion page.
4. Capture the `installSessionId` from backend logs or the persisted install-session row for that preview-started install.
5. Validate the backend success and portal endpoints:

```powershell
$api = 'https://api.app-sync.com'
$installSessionId = '<install-session-id from the HubSpot App Listing Preview flow>'

$marketplaceStatus = Invoke-RestMethod "$api/api/v1/marketplace/install/success?installSessionId=$installSessionId"
$marketplaceStatus | ConvertTo-Json -Depth 10

$portalId = $marketplaceStatus.portalId
Invoke-RestMethod "$api/api/v1/dashboard/overview?portalId=$portalId" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$api/api/v1/settings-store?portalId=$portalId" | ConvertTo-Json -Depth 10
```

## External paid install validation

```powershell
$api = 'https://api.app-sync.com'

$external = Invoke-RestMethod -Method Post -Uri "$api/api/v1/marketplace/install/start" -ContentType 'application/json' -Body (@{
  plan = 'professional'
  billingInterval = 'monthly'
  returnUrl = 'https://apps.app-sync.com/install/complete'
  tenantContext = @{
    source = 'external-routing-validation'
  }
  partnerUserId = 'manual-qa'
  partnerUserEmail = 'qa@app-sync.com'
  trialApproved = $false
} | ConvertTo-Json -Depth 5)

$external | ConvertTo-Json -Depth 10
Start-Process $external.checkoutUrl
```

After Stripe checkout and HubSpot auth complete in the browser, validate:

```powershell
$externalStatus = Invoke-RestMethod "$api/api/v1/marketplace/install/success?installSessionId=$($external.installSessionId)"
$externalStatus | ConvertTo-Json -Depth 10

$portalId = $externalStatus.portalId
Invoke-RestMethod "$api/api/v1/dashboard/overview?portalId=$portalId" | ConvertTo-Json -Depth 10
Invoke-RestMethod "$api/api/v1/settings-store?portalId=$portalId" | ConvertTo-Json -Depth 10
```
