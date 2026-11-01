const path = require('node:path');
module.exports = {
  packagerConfig: {
    asar: true,
    executableName: 'poliscope',
    extraResource: [path.join(__dirname, 'build/engine/poliscope-engine')],
  },
  hooks: {
    prePackage: async (_config, platform, arch) => {
      if (!['win32', 'linux'].includes(platform) || platform !== process.platform || arch !== 'x64' || process.arch !== 'x64') {
        throw new Error('Build natively on Windows x64 or Linux x64; cross-packaging is unsupported');
      }
    },
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
