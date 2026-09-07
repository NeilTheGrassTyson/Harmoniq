# DEV_SHARING.md

> How to let someone else use your local Harmoniq dev server, over Tailscale,
> without any traffic reaching the live site.
>
> This is the cheap option on purpose. It stands up nothing, costs nothing, and
> is reversible in one command. If you need a link that works while your machine
> is off, that is a real staging environment — a different, Tier 1 decision, and
> the row `docs/deployment.md` calls "Staging" describes a Railway service that
> does not exist yet.

---

## 1. What this gives you, and what it does not

A friend on your tailnet opens `https://<your-machine>.<tailnet>.ts.net` and
gets the branch you have checked out, running against the Neon **staging**
branch. They can sign up, rate, follow, and send Melodies. None of it is
visible on `harmoniq.live` and none of it touches the production database.

| | Where it points |
| --- | --- |
| Frontend | your `npm run dev`, served at `:443` |
| Backend | your `uvicorn`, served at `:8443` |
| Database | Neon `staging` — whatever `backend/.env` already says |
| Auth | your Clerk **development** instance |

**It is alive only while your machine is on and both servers are running.**
Closing the laptop ends the session. That is the trade for it being free.

**Everyone on your tailnet can reach it** once served. Tailscale Serve is
private to the tailnet — this is not `tailscale funnel`, which publishes to the
open internet. Do not use `funnel` here: it would put a dev build, with dev
Clerk keys and an open `/docs`, on a public URL.

---

## 2. Why the backend has to be served too

The obvious setup — serve the frontend and leave the backend on
`localhost:8000` — fails in a way that looks like a backend outage.

`NEXT_PUBLIC_API_URL` is read **by the browser**, not by the server. On your
friend's machine `localhost:8000` is *their* laptop, where nothing is
listening. Pages render (server-side fetches are fine) while every interactive
feature fails — the same signature as the CORS misconfiguration in ADR 0011,
and just as easy to misdiagnose.

So both processes get a tailnet address, on two ports.

---

## 3. Setup

### 3.1 Log in to Tailscale

The daemon is installed and running as a service but is not logged in
(`tailscale status` reports `NoState`). This step is interactive — it opens a
browser for you to authenticate:

```bash
"C:\Program Files\Tailscale\tailscale.exe" up
```

Then get your machine's MagicDNS name:

```bash
"C:\Program Files\Tailscale\tailscale.exe" status --json
```

Read `Self.DNSName` and drop the trailing dot. It looks like
`yourmachine.tailnet-name.ts.net`. Everything below calls that `$TSHOST`.

### 3.2 Point the two servers at each other

**`frontend/.env.local`** — the browser must reach the backend by its tailnet
name, not by loopback:

```
NEXT_PUBLIC_API_URL=https://$TSHOST:8443
HARMONIQ_DEV_TAILNET_HOST=$TSHOST
```

`NEXT_PUBLIC_*` values are inlined at build time; the dev server re-reads them
on restart, so restart `npm run dev` after editing this file.

`HARMONIQ_DEV_TAILNET_HOST` feeds `allowedDevOrigins` in `next.config.ts`.
Without it the page loads and then the dev assets and HMR fail on a blocked
cross-origin request — which reads as a broken build, not a blocked origin.

**`backend/.env`** — add the frontend's tailnet origin to CORS. Keep the
existing entries; localhost is still how *you* use it:

```
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,https://$TSHOST
```

No port on that origin — the frontend is served on 443. An origin missing here
breaks every browser call while server-rendered pages keep working.

Confirm `DATABASE_URL` in `backend/.env` is the **staging** branch before you
invite anyone. This is the one check that decides whether "messing around" is
harmless. `docs/deployment.md` §Database explains why the branch *named*
production is not necessarily the one being served — compare the `ep-…` host.

### 3.3 Start both servers, then serve them

```bash
cd backend && uvicorn app.main:app --reload
```

```bash
cd frontend && npm run dev
```

Then publish both to the tailnet (`--bg` keeps them running after the command
returns):

```bash
"C:\Program Files\Tailscale\tailscale.exe" serve --bg 3000
```

```bash
"C:\Program Files\Tailscale\tailscale.exe" serve --bg --https=8443 http://localhost:8000
```

Check what is exposed before sharing the link:

```bash
"C:\Program Files\Tailscale\tailscale.exe" serve status
```

### 3.4 Give your friend access

Tailscale → Machines → **Share** your machine, or invite them to the tailnet as
a user. Sharing a single node is the smaller grant; prefer it.

They open `https://$TSHOST` and sign up. Their account lands in your Clerk
**development** instance and their rows in Neon **staging** — separate from
every real user.

---

## 4. Taking it down

```bash
"C:\Program Files\Tailscale\tailscale.exe" serve reset
```

That withdraws both ports immediately. Revoke the share in the Tailscale admin
console as well if it was a one-off; a share outlives the serve.

Nothing in the repo needs reverting — `allowedDevOrigins` is absent whenever
`HARMONIQ_DEV_TAILNET_HOST` is unset.

---

## 5. Known limitations

- **Spotify linking will not work for them.** `SPOTIFY_REDIRECT_URI` must
  exactly match a URI registered in the Spotify dashboard, and the app is in
  Development Mode with a hard cap of 5 authorized users (see CLAUDE.md). Their
  account would have to be added there and the tailnet redirect URI registered.
  Everything that does not depend on Spotify works.
- **`/docs` and `/redoc` are open** on the served backend, because local
  `APP_ENV` is `development`. Fine on a private tailnet; another reason not to
  reach for `funnel`.
- **They see your branch, live.** Every save reloads their page. Useful when
  you are working together, disruptive when you are not — commit or stash
  before a session where they are reading rather than watching.
- **One machine, one tailnet name.** Two people cannot serve two branches at
  once from the same machine. Use a git worktree and a second port pair, or
  take turns.
