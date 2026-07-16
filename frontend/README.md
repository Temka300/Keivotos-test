# Keivotos frontend

The Waifu-Hoard interface is a Svelte 5, TypeScript, Vite, and Tailwind frontend.
The FastAPI application serves the production output from `frontend/dist`.

```powershell
npm.cmd ci
npm.cmd run check
npm.cmd run build
```

For live frontend development, run `npm.cmd run dev` here and start the backend
from the repository root with `uv run python app.py --dev --no-browser`.

API types live in `src/lib/api.ts`; shared state lives in `src/lib/stores.ts`;
view and settings components live in `src/components/`. Preserve the tested
product behavior and update the root changelog when changing a user-facing flow.
