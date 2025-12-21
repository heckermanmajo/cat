const esbuild = require('esbuild');
const fs = require('fs');
const path = require('path');

// Ensure dist directory exists
if (!fs.existsSync('dist')) {
  fs.mkdirSync('dist');
}

// Copy manifest.json into dist
fs.copyFileSync('src/manifest/manifest.json', 'dist/manifest.json');

// Copy popup.html into dist
fs.copyFileSync('src/popup/popup.html', 'dist/popup.html');

// Check if content script exists, create placeholder if not
const contentPath = 'src/content/index.js';
if (!fs.existsSync('src/content')) {
  fs.mkdirSync('src/content', { recursive: true });
}
if (!fs.existsSync(contentPath)) {
  fs.writeFileSync(contentPath, '// Content script placeholder\nconsole.log("Content script loaded");');
}

// Build all scripts
esbuild.build({
  entryPoints: {
    background: 'src/background/index.js',
    content: 'src/content/index.js',
    popup: 'src/popup/popup.js',
  },
  outdir: 'dist',
  bundle: true,
  minify: false,
  target: ['chrome90', 'firefox90'],
}).then(() => {
  console.log('Extension built successfully!');
  console.log('Load the extension from: browser-extension/dist');
}).catch(() => process.exit(1));
