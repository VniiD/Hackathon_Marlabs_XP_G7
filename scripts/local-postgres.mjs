import { createRequire } from "node:module";
import { homedir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { access, mkdir, readFile, rm, writeFile } from "node:fs/promises";

const projectRoot = resolve(fileURLToPath(new URL("..", import.meta.url)));
const dataDir = process.env.LOCAL_POSTGRES_DATA_DIR ?? join(homedir(), ".local/share/hackathon-xp-postgres");
const pidFile = join(dataDir, "runner.pid");
const packageRoot = process.env.LOCAL_POSTGRES_PACKAGE ?? join(homedir(), ".local/embedded-postgres");
const require = createRequire(join(packageRoot, "package.json"));
const EmbeddedPostgres = require("embedded-postgres").default;
const command = process.argv[2] ?? "start";
const port = Number(process.env.LOCAL_POSTGRES_PORT ?? process.env.DB_PORT ?? 5432);

if (command === "stop") {
  try {
    const pid = Number(await readFile(pidFile, "utf8"));
    process.kill(pid, "SIGTERM");
    console.log(`Parada solicitada ao processo ${pid}.`);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
    console.log("PostgreSQL local não está em execução.");
  }
  process.exit(0);
}

if (!new Set(["init", "start"]).has(command)) {
  throw new Error("Uso: node scripts/local-postgres.mjs [init|start|stop]");
}

const postgres = new EmbeddedPostgres({
  databaseDir: dataDir,
  port,
  user: "postgres",
  password: "postgres",
  persistent: true,
  postgresFlags: ["-c", "timezone=America/Sao_Paulo"],
});

try {
  await access(join(dataDir, "PG_VERSION"));
} catch (error) {
  if (error.code !== "ENOENT") throw error;
  await postgres.initialise();
}
if (command === "init") {
  console.log(`Cluster PostgreSQL inicializado em ${dataDir}.`);
  process.exit(0);
}

await postgres.start();
const admin = postgres.getPgClient("postgres", "127.0.0.1");
await admin.connect();
const exists = await admin.query("SELECT 1 FROM pg_database WHERE datname = 'advisor'");
if (exists.rowCount === 0) await postgres.createDatabase("advisor");
await admin.end();

const db = postgres.getPgClient("advisor", "127.0.0.1");
await db.connect();
const schemaExists = await db.query("SELECT to_regclass('public.users') AS users");
if (!schemaExists.rows[0].users) {
  await db.query(await readFile(join(projectRoot, "db/01_schema.sql"), "utf8"));
  await db.query(await readFile(join(projectRoot, "db/02_seed.sql"), "utf8"));
}
await db.end();

await mkdir(dataDir, { recursive: true });
await writeFile(pidFile, String(process.pid));
console.log(`PostgreSQL ativo em 127.0.0.1:${port}/advisor. Ctrl+C encerra o serviço.`);

let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  await postgres.stop();
  await rm(pidFile, { force: true });
  process.exit(0);
}

process.once("SIGINT", stop);
process.once("SIGTERM", stop);
setInterval(() => {}, 60_000);
