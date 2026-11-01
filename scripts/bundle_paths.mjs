/** @electron/asar listPackage uses the host separator, including on Windows. */
export function bundlePathsAreSafe(entries, separator) {
  if (separator !== '/' && separator !== '\\') return false;
  return entries.every(entry => {
    const name = entry.split(separator).join('/');
    return name === '/package.json' || name === '/.vite' || name.startsWith('/.vite/');
  });
}
