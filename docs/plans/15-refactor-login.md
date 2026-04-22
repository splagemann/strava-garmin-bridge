# Plan for #15: Refactor login

Issue: https://github.com/splagemann/strava-garmin-bridge/issues/15

## Goal

Make Strava the primary application login and move Garmin setup into the authenticated app as an optional connection, matching the current Withings pattern.

Today the backend already creates the local `User` and JWT from Strava OAuth in `backend/app/routes/auth.py`, but the frontend still treats Garmin as part of login completion:

- `frontend/src/hooks/useAuth.ts` returns `isAuthenticated` only when both `strava_connected` and `garmin_connected` are true.
- `frontend/src/App.tsx` redirects authenticated Strava users back to `/auth` until Garmin is connected.
- `frontend/src/pages/AuthPage.tsx` navigates to `/` only after both Strava and Garmin are connected and renders Garmin setup as step 3 of login.
- Dashboard connection status in `frontend/src/pages/DashboardPage.tsx` assumes Garmin is connected.

The target behavior is:

- A Strava OAuth token/JWT is sufficient to enter the app.
- Garmin credentials remain connectable after login, as an optional integration similar to Withings.
- Garmin-dependent sync actions still require Garmin and should guide the user to connect it instead of failing silently.
- Existing users with Garmin connected keep working without migration.

## Affected Areas

Backend:

- `backend/app/routes/auth.py`
  - Keep `/api/v1/auth/strava/auth-url` and `/api/v1/auth/strava/exchange` as the login flow.
  - Keep `/api/v1/auth/garmin/credentials` and `/api/v1/auth/garmin/mfa` protected by `get_current_user`, making Garmin explicitly post-login.
  - Keep `/api/v1/auth/status` as the single source for `strava_connected`, `garmin_connected`, `garmin_requires_mfa`, and `withings_connected`.
- `backend/app/models/auth.py` and `backend/app/models/user.py`
  - No schema change expected. `GarminAuth` is already optional by relationship and by separate table.
- `backend/app/routes/sync.py`
  - Manual Strava -> Garmin and Garmin -> Strava endpoints already return `400 "Garmin not connected"` if missing. Preserve this behavior and ensure frontend handles it.
- `backend/app/routes/activities.py`
  - `/activities/garmin` already checks Garmin before reading Garmin activities. `/activities/strava` can continue working for Strava-only users.
- `backend/app/tasks/sync_tasks.py`
  - Periodic Strava and Garmin polling already skip users without Garmin. Confirm this remains intentional once Strava-only users are allowed in the app.
- `backend/app/services/weight_sync_service.py`
  - Withings -> Garmin already requires both Withings and Garmin; keep Garmin as optional globally but required for this specific sync.

Frontend:

- `frontend/src/hooks/useAuth.ts`
  - Change `isAuthenticated` to mean the user has a valid app session and Strava is connected: `!!authStatus?.strava_connected`.
  - Keep `hasAuthToken` as the fast check for whether to request `/auth/status`.
- `frontend/src/App.tsx`
  - `ProtectedRoute` should allow users through when `hasAuthToken` is true and `authStatus.strava_connected` is true.
  - Do not require `garmin_connected` for app access.
- `frontend/src/pages/AuthPage.tsx`
  - Make this page a Strava login page first.
  - If the user already has a valid Strava session, navigate to `/` without requiring Garmin.
  - Remove Garmin setup from the unauthenticated login completion path, or render it only as an optional post-login connection entry point consistent with Withings.
- `frontend/src/pages/DashboardPage.tsx`
  - Show Garmin as connected, disconnected, or MFA-required based on `authStatus`.
  - Add an in-app Garmin connection action near the existing Withings connection action.
  - Avoid presenting Garmin-dependent sync forms/actions as ready when Garmin is missing.
- `frontend/src/components/ActivitiesList.tsx`
  - It currently fetches both Strava and Garmin activities together. Update it so Strava activities still load for Strava-only users and Garmin activities are fetched only when `authStatus.garmin_connected` is true.
  - Disable or hide "sync to Garmin" and Garmin-source actions when Garmin is not connected.
- `frontend/src/api/auth.ts` and `frontend/src/types/auth.ts`
  - Existing Garmin credential/MFA API methods can stay. Confirm response types cover `requires_mfa`.
- Tests:
  - `frontend/src/hooks/useAuth.test.tsx`
  - `frontend/src/App.test.tsx`
  - `frontend/src/pages/AuthPage.test.tsx`
  - Add or adjust dashboard/activity-list tests if UI gating changes there.
  - Backend route tests can stay focused unless endpoint semantics change.

Docs likely needing follow-up in the implementation PR:

- `README.md`, `docs/SECURITY.md`, and `frontend/README.md` describe login/setup as connecting both Strava and Garmin. Update wording after the implementation so user-facing docs match the new flow.

## Proposed Approach

1. Keep Strava OAuth as the only app-login mechanism.
   - Leave backend Strava exchange behavior intact: exchange code, find/create `User`, save `StravaAuth`, issue JWT.
   - Do not add a Garmin-backed identity path.
   - Do not require Garmin in `/api/v1/auth/status`.

2. Loosen the frontend authenticated route gate.
   - In `useAuth`, compute `isAuthenticated` from Strava status only.
   - In `ProtectedRoute`, keep the existing `hasAuthToken` and loading behavior, then allow access once Strava is connected.
   - If `/auth/status` fails or returns no Strava connection, keep redirecting to `/auth`.

3. Split login from optional integrations.
   - Update `AuthPage` so the primary state is "Connect with Strava".
   - Redirect to `/` once `authStatus.strava_connected` is true.
   - Move Garmin credential/MFA UI out of the required login sequence. The simplest low-risk option is to reuse the existing Garmin form in `DashboardPage` under the Connections section, next to Withings.
   - Keep Withings as optional and only visible after Strava login, as it is now.

4. Make Dashboard connection handling explicit.
   - Render Strava as the primary connected account.
   - Render Garmin as:
     - connected when `authStatus.garmin_connected` is true,
     - action-required when `authStatus.garmin_requires_mfa` is true,
     - connectable when neither is true.
   - Render Withings as the existing optional OAuth connection.
   - Keep connection mutations invalidating `QUERY_KEYS.authStatus` so the dashboard updates immediately after Garmin credentials or MFA.

5. Gate Garmin-dependent features in the UI.
   - Manual Strava -> Garmin sync requires Garmin. Disable the submit action or show a connect-Garmin prompt when missing.
   - Manual Garmin -> Strava sync requires Garmin. Hide or disable that tab when missing.
   - `ActivitiesList` should always support Strava activities for Strava-only users. Fetch Garmin activities only when Garmin is connected and avoid `Promise.all` failure of the entire list when Garmin is unavailable.
   - Withings -> Garmin sync status should remain optional; if Withings is connected but Garmin is missing, show Garmin as the missing dependency.

6. Preserve backend guards.
   - Keep the existing `400` checks in `backend/app/routes/sync.py` and `backend/app/routes/activities.py` for Garmin-specific operations.
   - This ensures direct API calls cannot perform Garmin sync without credentials even though the app login succeeds with only Strava.

7. Update tests around the new contract.
   - `useAuth.test.tsx`: assert `isAuthenticated` is true for `{ strava_connected: true, garmin_connected: false }`.
   - `App.test.tsx`: add coverage for a token plus Strava-only auth status rendering protected content.
   - `AuthPage.test.tsx`: update redirect expectation to Strava-only and remove "fully connected" login requirement.
   - Add UI tests for Dashboard or ActivitiesList so Garmin controls are gated for Strava-only users.
   - Keep existing backend tests unless backend response shapes are changed.

## Edge Cases

- Existing local storage token with Strava connected but Garmin missing should now enter the app instead of looping back to `/auth`.
- Existing local storage token with no valid Strava auth should still land on `/auth`.
- Garmin MFA pending (`garmin_requires_mfa: true`, `garmin_connected: false`) should not block app entry, but should show a clear path to complete Garmin setup.
- Failed Garmin credential verification should not log the user out or redirect them to login.
- Strava-only users should be able to view Strava activities, filters, sync history, and connection settings where those pages do not require Garmin.
- Strava -> Garmin, Garmin -> Strava, Garmin activities, and Withings -> Garmin must remain unavailable until Garmin is connected.
- `ActivitiesList` should avoid failing the whole component when only the Garmin activities request fails because Garmin is not connected.
- Periodic background tasks should continue skipping users without Garmin instead of generating failed sync logs for every Strava-only user.
- Placeholder Strava email values like `athlete_<id>@strava.local` should continue to work as user identity keys unless a separate account-linking issue changes that.

## Validation

Automated:

- Frontend:
  - `cd frontend && npm test -- --run`
  - Focused during development:
    - `cd frontend && npm test -- --run src/hooks/useAuth.test.tsx`
    - `cd frontend && npm test -- --run src/App.test.tsx src/pages/AuthPage.test.tsx`
- Backend:
  - `cd backend && pytest`
  - Focused if backend guards are touched:
    - `cd backend && pytest tests/routes tests/services`

Manual:

- Start the app with the documented dev stack.
- Visit `/auth` without a token and confirm only Strava is required for login.
- Complete Strava OAuth and confirm the app lands on `/` with `garmin_connected: false`.
- Confirm Dashboard shows Strava connected and Garmin/Withings as optional connection actions.
- Try Strava-only activity browsing and any non-Garmin pages that should remain available.
- Attempt a Strava -> Garmin sync while Garmin is missing and confirm the UI blocks it or shows the backend `Garmin not connected` error cleanly.
- Add Garmin credentials. If MFA is required, confirm the MFA state is shown in-app and successful verification updates connection status.
- After Garmin connects, confirm both manual sync directions and Garmin activity fetching are available again.
- Connect Withings with and without Garmin connected and confirm Withings remains optional while Withings -> Garmin clearly depends on Garmin.
