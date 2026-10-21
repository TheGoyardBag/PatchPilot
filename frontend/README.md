# Optional Next.js frontend

The verified no-build dashboard is served by FastAPI at port 8000. This folder is
an independent React / Next.js / TypeScript implementation of the same workflow.
It calls the exact same authenticated API; it does not embed the no-build UI.

```bash
npm install
npm run typecheck
npm run build
npm run start
```

Keep FastAPI running at `http://127.0.0.1:8000`; open `http://127.0.0.1:3000`.
The server-side rewrite forwards `/api/*` to the loopback backend. Credentials
stay in browser session storage and are sent as bearer headers. The provider key
never goes to the frontend. There are no server actions or unauthenticated writes.

Next 16.4.1 and React 19.3 are specified. `npm install` must create a real lockfile;
commit it after successful installation and validation. No lockfile or successful
production build is fabricated. See `../reports/VALIDATION.md` for build status.

This remains a local single-user application. Add TLS, real user identity,
tenant isolation, a hardened remote runner fleet, and deployment-specific headers
before exposing it publicly.
