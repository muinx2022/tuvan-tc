# Web App

Next.js frontend for the public site and authenticated workspace.

## Commands

```bash
npm install
npm run dev
npm run build
npm run lint
```

Default local URL: `http://localhost:3000`

## Environment

Create `.env.local` if you need to override the API base URL:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080/api/v1
```

## Notes

- API requests are centralized in `src/lib/api.ts`.
- Global styling and layout live under `src/app/`.
