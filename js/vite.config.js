import { defineConfig } from "vite";
import { fileURLToPath } from "url"
import { dirname, resolve } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  build: {
    outDir: "../request_ddi/static/js/",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        base: resolve(__dirname, "src/base.js"),
        export: resolve(__dirname, "src/export.js"),
        questionDetail: resolve(__dirname, "src/question_detail.js"),
        searchResults: resolve(__dirname, "src/search_results/init.js"),
        uploadCsv: resolve(__dirname, "src/upload_csv_collection.js"),
        uploadXml: resolve(__dirname, "src/upload_xml.js"),
      },
      output: {
        entryFileNames: "[name].bundle.js",
        chunkFileNames: "chunks/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  },

  server: {
    port: 3000,
    open: false,
    // Important pour Docker en dev
    host: "0.0.0.0",
    watch: {
      usePolling: true
    }
  }
});