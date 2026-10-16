// Monaco, bundled locally by Vite (no CDN loader), so offline lab demos work.
// Only the editor core, the C language and the base editor worker are included.
import * as monaco from 'monaco-editor/editor/editor.api.js'
import 'monaco-editor/languages/definitions/cpp/register.js'
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker'

type MonacoGlobal = typeof globalThis & { MonacoEnvironment?: monaco.Environment }

;(globalThis as MonacoGlobal).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
}

export { monaco }
