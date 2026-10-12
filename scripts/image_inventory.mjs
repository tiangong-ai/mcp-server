import { readFileSync } from 'node:fs';
import { join } from 'node:path';
const manifest = JSON.parse(readFileSync('/app/package.json', 'utf8'));
const dependencies = Object.fromEntries(
  Object.keys(manifest.dependencies)
    .sort()
    .map((name) => [
      name,
      JSON.parse(readFileSync(join('/app/node_modules', name, 'package.json'), 'utf8')).version,
    ]),
);
console.log(
  JSON.stringify(
    {
      sourceRevision: process.env.SOURCE_REVISION,
      packageVersion: manifest.version,
      node: process.version,
      architecture: process.arch,
      dependencies,
    },
    null,
    2,
  ),
);
