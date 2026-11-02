import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// base './' lets the built site work from any sub-path, e.g. https://<user>.github.io/aralwatch/
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  resolve: {alias: {'@': path.resolve(__dirname, '.')}},
});
