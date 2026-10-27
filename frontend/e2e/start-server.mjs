// Starts the API in demo mode on a throwaway demo database for the end-to-end tests.
// The local development database (lagerflow.db) is never touched.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..", "..");
const venvPython = [join(root, ".venv", "Scripts", "python.exe"), join(root, ".venv", "bin", "python")];
const python = process.env.PYTHON ?? venvPython.find(existsSync) ?? "python";
const dbFile = join(mkdtempSync(join(tmpdir(), "lagerflow-e2e-")), "lagerflow-demo.db");

const env = {
  ...process.env,
  LAGERFLOW_DEMO_MODE: "true",
  LAGERFLOW_DATABASE_URL: `sqlite:///${dbFile.replaceAll("\\", "/")}`,
};
const options = { cwd: root, env, stdio: "inherit" };

const migrate = spawnSync(python, ["-m", "alembic", "upgrade", "head"], options);
if (migrate.status !== 0) process.exit(migrate.status ?? 1);

const port = process.env.E2E_PORT ?? "8765";
const server = spawn(python, ["-m", "uvicorn", "app.main:app", "--port", port], options);
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => server.kill());
server.on("exit", (code) => process.exit(code ?? 0));
