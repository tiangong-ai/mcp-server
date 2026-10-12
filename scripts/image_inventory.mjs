import { existsSync, readFileSync, readdirSync } from 'node:fs';
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
const resolvedPackages = {};
function inventory(directory, prefix = '') {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    if (!entry.isDirectory() || entry.name.startsWith('.')) continue;
    const location = join(directory, entry.name);
    if (entry.name.startsWith('@')) {
      inventory(location, `${prefix}${entry.name}/`);
      continue;
    }
    const packagePath = join(location, 'package.json');
    if (!existsSync(packagePath)) continue;
    const name = `${prefix}${entry.name}`;
    resolvedPackages[name] = JSON.parse(readFileSync(packagePath, 'utf8')).version;
    if (existsSync(join(location, 'node_modules'))) {
      inventory(join(location, 'node_modules'), `${name}/node_modules/`);
    }
  }
}
inventory('/app/node_modules');
console.log(
  JSON.stringify(
    {
      sourceRevision: process.env.SOURCE_REVISION,
      packageVersion: manifest.version,
      node: process.version,
      architecture: process.arch,
      dependencies,
      resolvedPackages,
    },
    null,
    2,
  ),
);
