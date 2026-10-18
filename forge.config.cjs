const path = require('node:path');
module.exports = {
  packagerConfig: {
    asar: true,
    executableName: 'poliscope',
    extraResource: [path.join(__dirname, 'build/engine/poliscope-engine')],
  },
  makers: [],
  plugins: [{ name: '@electron-forge/plugin-vite', config: {
    build: [
      { entry: 'desktop/main/index.ts', config: 'vite.main.config.mts', target: 'main' },
      { entry: 'desktop/preload/index.ts', config: 'vite.preload.config.mts', target: 'preload' },
    ],
    renderer: [{ name: 'main_window', config: 'vite.renderer.config.mts' }],
  }}],
};
