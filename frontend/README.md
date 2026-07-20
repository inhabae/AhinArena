# AhinArena Frontend

React/Vite application for AhinArena. It uses React Router for the app shell,
match flows, auth pages, player profiles, bot profiles, and replay views.

## Local Development

Run the FastAPI backend on `http://127.0.0.1:8000`, then start Vite:

```sh
npm install
npm run dev
```

The dev server usually runs at `http://localhost:5173`. `vite.config.js`
proxies `/api/*` browser requests to the local backend and strips the `/api`
prefix.

## Scripts

- `npm run dev` starts the local Vite server.
- `npm run build` creates the production static bundle in `dist/`.
- `npm run lint` runs Oxlint.

See `../docs/frontend.md` for the route map, API client conventions, and replay
behavior.
