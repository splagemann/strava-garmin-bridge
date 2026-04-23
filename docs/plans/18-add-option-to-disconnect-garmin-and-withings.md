# Plan for #18: Add Option to Disconnect Garmin and Withings

Issue: https://github.com/splagemann/strava-garmin-bridge/issues/18

## Goal

Add dashboard controls to disconnect Garmin and Withings after they have been connected.

This issue is downstream of `docs/plans/15-refactor-login.md`, because the requested UI change explicitly says to remove Strava from the dashboard connections section once Strava is the primary login. The implementation for #18 should therefore assume:

- Strava remains the required app login and is not disconnectable from the dashboard.
- The dashboard connections section only manages optional integrations.
- Garmin and Withings can be connected and disconnected independently after login.

Today the repo supports:

- Garmin connect via stored encrypted credentials and optional MFA in `backend/app/routes/auth.py` and `backend/app/services/garmin_service.py`.
- Withings connect via OAuth token exchange in `backend/app/routes/auth.py` and `backend/app/services/withings_service.py`.
- Dashboard connection status rendering in `frontend/src/pages/DashboardPage.tsx`.

What is missing is a first-class disconnect path in both the backend and frontend.

## Affected Areas

Backend:

- `backend/app/routes/auth.py`
  - Add authenticated disconnect endpoints for Garmin and Withings.
  - Keep `/api/v1/auth/status` as the source of truth for connection state after disconnect.
- `backend/app/services/garmin_service.py`
  - Add a repo-local method to delete or clear the user’s Garmin auth record.
- `backend/app/services/withings_service.py`
  - Add a repo-local method to delete the user’s Withings auth record.
- `backend/app/models/auth.py`
  - No schema change is required if disconnect is implemented as deleting existing `GarminAuth` and `WithingsAuth` rows.
- `backend/app/tasks/sync_tasks.py`
  - No feature changes required, but disconnect semantics must stay compatible with the existing `if not user.garmin_auth` and `if not user.withings_auth` guards.
- `backend/app/routes/sync.py`
  - Existing guards should continue returning clean errors when Garmin has been disconnected.
- `backend/app/services/weight_sync_service.py`
  - Existing `withings_auth` and `garmin_auth` dependency checks should naturally stop weight sync once either integration is removed.
- Tests likely to add:
  - `backend/tests/routes/` for disconnect endpoints and updated auth status behavior.
  - Possibly `backend/tests/services/` for service-level deletion helpers if that logic becomes non-trivial.

Frontend:

- `frontend/src/pages/DashboardPage.tsx`
  - Remove Strava from the connections section once #15 behavior is in place.
  - Replace the current read-only connected badges for Garmin and Withings with connect/disconnect actions.
- `frontend/src/hooks/useAuth.ts`
  - Add disconnect mutations and keep `QUERY_KEYS.authStatus` invalidated after connect and disconnect.
- `frontend/src/api/auth.ts`
  - Add authenticated API methods for disconnecting Garmin and Withings.
- `frontend/src/types/auth.ts`
  - Existing `AuthStatus` shape is likely sufficient unless the UI needs a new explicit flag.
- `frontend/src/pages/DashboardPage.test.tsx`
  - Extend coverage for disconnect actions, the absence of Strava in the connections section, and post-disconnect UI state.
- Potentially `frontend/src/hooks/useAuth.test.tsx`
  - Add mutation coverage for the new disconnect methods.

Related context:

- `frontend/src/components/ActivitiesList.tsx`
  - Already uses `authStatus.garmin_connected` to gate Garmin-specific actions. This behavior should remain correct after disconnect.
- `frontend/src/pages/WithingsCallbackPage.tsx`
  - No direct changes expected, but disconnect must not break reconnect after a previous connection existed.

## Proposed Approach

1. Treat disconnect as removal of the integration record, not as a soft-disabled flag.
   - For Garmin, delete the user’s `GarminAuth` row.
   - For Withings, delete the user’s `WithingsAuth` row.
   - This matches the current repo contract, where connection status is derived from whether the related auth record exists and, for Garmin, whether session data exists.
   - Avoid a schema migration unless implementation uncovers a strong reason to preserve historical inactive auth rows.

2. Add backend disconnect endpoints under the existing auth router.
   - Add something like `DELETE /api/v1/auth/garmin` and `DELETE /api/v1/auth/withings` in `backend/app/routes/auth.py`.
   - Protect both with `get_current_user`.
   - Return a small success payload such as `{ "message": "Garmin disconnected successfully" }`.
   - Make repeated disconnect calls idempotent from the client’s perspective.
   - Preferred behavior: return success even when already disconnected, so the UI can safely refresh state without special casing.

3. Encapsulate deletion logic in service methods instead of deleting records inline in the route.
   - Add `disconnect(user)` or equivalent methods to:
     - `backend/app/services/garmin_service.py`
     - `backend/app/services/withings_service.py`
   - Garmin disconnect should remove all persisted Garmin secrets and session state by deleting the row rather than merely nulling columns.
   - Withings disconnect should remove stored OAuth access and refresh tokens by deleting the row.
   - Keep the route layer thin and leave persistence behavior centralized.

4. Keep `auth_status` as the only frontend source of truth after mutation.
   - No optimistic state rewrite is needed.
   - After disconnect, the frontend should invalidate and refetch `QUERY_KEYS.authStatus`.
   - This keeps Garmin MFA edge cases aligned with backend truth and avoids UI drift.

5. Update the dashboard connections UX for the post-#15 world.
   - Remove the Strava badge from the dashboard connections section once #15 lands.
   - Garmin:
     - When disconnected, keep the existing connect form and MFA flow.
     - When connected, show a disconnect button instead of only a green badge.
     - If `garmin_requires_mfa` is true and `garmin_connected` is false, treat it as an incomplete connection, not a connected state. Do not show a disconnect button unless the team decides users should be allowed to cancel the pending Garmin setup.
   - Withings:
     - When disconnected, keep the existing `Connect Withings` button.
     - When connected, show a disconnect button next to or instead of the connected badge.
   - Use confirmation UX before disconnect if the current dashboard style already supports destructive confirmation. If not, a simple browser confirm is an acceptable low-scope first step.

6. Preserve the current downstream behavior after disconnect.
   - Garmin disconnect should automatically disable:
     - manual Strava -> Garmin sync
     - manual Garmin -> Strava sync
     - Garmin activity fetches
     - Withings -> Garmin weight sync
     - background Garmin-related task processing for that user
   - Withings disconnect should automatically disable Withings weight import while leaving Garmin activity sync untouched.
   - These behaviors already follow from current guards, so the implementation should lean on those existing checks rather than adding duplicate state.

7. Add repo-specific tests around the new contract.
   - Backend:
     - disconnect Garmin when connected
     - disconnect Garmin when already disconnected
     - disconnect Withings when connected
     - disconnect Withings when already disconnected
     - `GET /api/v1/auth/status` reflects the disconnected state immediately afterward
   - Frontend:
     - dashboard renders disconnect controls for connected Garmin/Withings
     - clicking disconnect calls the right hook/API method
     - after disconnect, the UI falls back to `Connect Garmin` or `Connect Withings`
     - Strava no longer appears in the connections section after the #15 assumptions are applied

## Repo-Specific Notes

- Garmin connection state is currently not just `user.garmin_auth is not None`; `backend/app/routes/auth.py` marks Garmin connected only when `session_data` exists.
- Garmin MFA pending state is tracked separately via `encrypted_mfa_token`.
- Because of that split, deleting the Garmin auth row is cleaner than nulling selected fields and trying to preserve partial state.
- Withings connection state is simpler: `current_user.withings_auth is not None`.
- Existing periodic task guards in `backend/app/tasks/sync_tasks.py` already assume disconnect means the related auth row is absent.
- Existing frontend gating in `frontend/src/components/ActivitiesList.tsx` already reacts correctly to `authStatus.garmin_connected === false`, so no special disconnect-only path should be needed there.

## Edge Cases

- Disconnect Garmin while a Garmin MFA challenge is pending.
  - Decide whether the disconnect action should be available in this state.
  - Recommended: yes, and it should delete the pending `GarminAuth` row so the user can fully reset the setup flow.

- Disconnect Garmin after credentials are saved but before a valid session is restored.
  - The backend should still treat this as a normal disconnect and remove stored encrypted credentials.

- Disconnect Withings when tokens are expired.
  - Disconnect should delete local credentials only and should not depend on a successful remote API call.

- Repeated disconnect clicks or a stale UI retry.
  - Endpoint should be idempotent so the second request still resolves cleanly.

- Disconnect during active background processing.
  - Already-queued jobs may still start with stale user state, but subsequent guards should fail cleanly once the job reloads the user or attempts to access missing auth.
  - The implementation does not need a job cancellation system for this issue.

- Disconnect Garmin while Withings remains connected.
  - Weight sync should stop because `WeightSyncService` already requires both integrations.
  - The dashboard should make it clear that Withings can stay connected independently even though weight sync is blocked without Garmin.

- Disconnect Withings while Garmin remains connected.
  - Activity sync continues to work.
  - Only Withings-specific features should disappear.

- Future interaction with issue #15.
  - If #15 has not landed yet, the implementation PR for #18 should either stack on top of #15 or explicitly include the minimal UI reshaping needed to remove Strava from the connections section without reintroducing the old login assumptions.

## Validation

Backend automated validation:

- `cd backend && pytest`
- Focused runs if route tests are added:
  - `cd backend && pytest tests/routes tests/services`

Frontend automated validation:

- `cd frontend && npm test -- --run`
- Focused runs:
  - `cd frontend && npm test -- --run src/pages/DashboardPage.test.tsx src/hooks/useAuth.test.tsx`

Manual validation in this repo’s flow:

1. Log in with Strava and confirm the dashboard connections section does not show Strava anymore once #15 behavior is present.
2. Connect Garmin and confirm the dashboard shows Garmin as connected with a disconnect action.
3. Disconnect Garmin and confirm:
   - the Garmin connection card switches back to the connect form
   - Garmin sync buttons become unavailable
   - Garmin activity views and Garmin-specific dashboard actions stop working cleanly
   - `GET /api/v1/auth/status` returns `garmin_connected: false`
4. Connect Withings and confirm the dashboard shows Withings as connected with a disconnect action.
5. Disconnect Withings and confirm:
   - the dashboard switches back to `Connect Withings`
   - `GET /api/v1/auth/status` returns `withings_connected: false`
   - Garmin activity sync remains unaffected if Garmin is still connected
6. If Garmin MFA is required, start Garmin setup, then disconnect, and confirm the next Garmin connect attempt starts from a clean state.

## Out of Scope

- Disconnecting Strava from inside the authenticated dashboard.
- Changing the login architecture beyond the dependency on #15.
- Revoking Garmin or Withings tokens/sessions with the upstream provider if those APIs are not already integrated here.
- Adding new database columns or migrations unless implementation reveals a real persistence requirement that cannot be met by deleting auth rows.
