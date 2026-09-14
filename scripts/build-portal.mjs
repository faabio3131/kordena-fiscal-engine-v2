import { cp, mkdir, rm, stat } from "node:fs/promises";
import { resolve } from "node:path";

const root = process.cwd();
const source = resolve(root, "portal");
const target = resolve(root, "dist", "portal");

await stat(resolve(source, "index.html"));
await stat(resolve(source, "app.js"));
await stat(resolve(source, "styles.css"));
await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
await cp(source, target, { recursive: true });
console.log(`Portal build ready at ${target}`);
