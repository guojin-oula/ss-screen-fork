#!/usr/bin/env python3
"""Targeted SS-Screen viewer layout + JSON switching optimization.

Run from repository root: python3 apply_ssscreen_viewer_optimization.py
Only edits source and adds an inline CSS fallback to the already-built HTML.
It never touches the functional WebGL2 JS bundle or .ssproject files.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()
APP = Path('gui-matterviz/src/App.svelte')
CSS = Path('gui-matterviz/src/style.css')
GUI = Path('src/ssscreen/gui/visualization.py')
DIST_HTML = Path('src/ssscreen/gui/matterviz_dist/index.html')
FILES = [APP, CSS, GUI, DIST_HTML]

LAYOUT_RULES = '''
/* SS-Screen embedded MatterViz: fill the QWebEngineView, not the docs page. */
:root {
  --struct-width: 100%;
  --struct-height: 100%;
  --struct-max-width: 100%;
}
html, body, #app {
  width: 100% !important;
  height: 100% !important;
  min-height: 0 !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  overflow: hidden;
}
body { display: block !important; }
#app > main {
  box-sizing: border-box;
  display: grid !important;
  grid-template-rows: 38px minmax(0, 1fr) !important;
  width: 100% !important;
  height: 100% !important;
  min-width: 0 !important;
  min-height: 0 !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
  flex: none !important;
}
#app > main > section {
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  max-width: none;
  overflow: hidden;
}
#app > main > section > .structure {
  --struct-width: 100%;
  --struct-height: 100%;
  --struct-max-width: 100%;
  width: 100% !important;
  height: 100% !important;
  max-width: none !important;
  min-width: 0;
  min-height: 0;
}
'''.strip()
LAYOUT_MARKER = 'SS-Screen embedded MatterViz: fill the QWebEngineView'
SPEED_MARKER = 'SS-Screen JSON switch cache'

LOAD_BLOCK = '''  // SS-Screen JSON switch cache: reuse the parsed data and the mounted viewer.
  let latestLoadId = 0
  const parsedStructures = new Map()
  const MAX_CACHED = 4

  window.ssScreenLoadStructure = async (
    content,
    filename = 'structure.json',
    label = filename,
  ) => {
    const id = ++latestLoadId
    try {
      const cached = parsedStructures.get(filename)
      let nextStructure
      if (cached && cached.content === content) {
        // Updating the same structure twice need not re-run the parser.
        nextStructure = cached.structure
        parsedStructures.delete(filename)
        parsedStructures.set(filename, cached)
      } else {
        const opened = await open_material({ data: content, filename })
        if (id !== latestLoadId) return  // A more recent selection won.
        if (opened.type !== 'structure') {
          structure = null
          title = label
          message = 'MatterViz could not recognize this structure.'
          return
        }
        nextStructure = opened.data
        parsedStructures.delete(filename)
        parsedStructures.set(filename, { content, structure: nextStructure })
        while (parsedStructures.size > MAX_CACHED) {
          parsedStructures.delete(parsedStructures.keys().next().value)
        }
      }
      if (id !== latestLoadId) return
      structure = nextStructure  // Reactive prop update; no component remount.
      title = label
      message = ''
    } catch (error) {
      if (id !== latestLoadId) return
      structure = null
      title = label
      message = `Structure load failed: ${error?.message ?? error}`
      console.error('SSSCREEN_STRUCTURE_LOAD_ERROR', error)
    }
  }

'''


def patch_app(text: str) -> str:
    if SPEED_MARKER in text:
        return text
    start = text.find('  window.ssScreenLoadStructure = async (')
    end = text.find('  window.ssScreenClearStructure = () => {', start)
    if start < 0 or end < 0:
        raise ValueError('App.svelte: could not locate original ssScreenLoadStructure block')
    text = text[:start] + LOAD_BLOCK + text[end:]
    text, count = re.subn(r'^\s*let structureKey\s*=\s*0\s*\n', '\n', text, count=1, flags=re.M)
    if count != 1:
        raise ValueError('App.svelte: expected structureKey declaration')
    text, count = re.subn(r'^\s*structureKey\s*\+=\s*1\s*\n', '', text, count=1, flags=re.M)
    # The increment is already replaced with the old loading block.
    if count != 0:
        raise ValueError('App.svelte: old structureKey increment remains outside load block')
    text, count = re.subn(
        r'\{#key\s+structureKey\s*\}\s*(<Structure\s+[\s\S]*?\/>)\s*\{\/key\}',
        lambda m: m.group(1), text, count=1,
    )
    if count != 1:
        raise ValueError('App.svelte: expected one keyed Structure component')
    clear = '  window.ssScreenClearStructure = () => {\n'
    if text.count(clear) != 1:
        raise ValueError('App.svelte: expected one clear handler')
    text = text.replace(clear, clear + '    latestLoadId += 1\n', 1)
    if '{#key structureKey}' in text:
        raise ValueError('App.svelte: failed to remove keyed Structure')
    return text


def patch_css(text: str) -> str:
    if LAYOUT_MARKER in text:
        return text
    return text.rstrip() + '\n\n' + LAYOUT_RULES + '\n'


def patch_gui(text: str) -> str:
    if 'def _queue_selection_change(self, index: int)' in text:
        return text
    start = text.index('class StructureResultsPage(QWidget):')
    end = text.index('\n\nclass ScaledImage(', start)
    prefix, block, suffix = text[:start], text[start:end], text[end:]
    old = 'from PySide6.QtCore import QPointF, Qt, QUrl'
    if old not in prefix:
        if 'QTimer' not in prefix:
            raise ValueError('visualization.py: unexpected QtCore import')
    else:
        prefix = prefix.replace(old, 'from PySide6.QtCore import QPointF, Qt, QUrl, QTimer', 1)

    old_connection = '        self.selector.activated.connect(self._selection_changed)'
    new_connection = '''        # Debounce rapid combo-box choices; only the last one is rendered.
        self._pending_selection_index = -1
        self._last_structure_signature = None
        self._selection_timer = QTimer(self)
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(160)
        self._selection_timer.timeout.connect(self._apply_pending_selection)
        self.selector.activated.connect(self._queue_selection_change)'''
    if block.count(old_connection) != 1:
        raise ValueError('visualization.py: expected one QComboBox activated connection')
    block = block.replace(old_connection, new_connection, 1)

    old_refresh = '    def refresh(self) -> None:\n        current = self.selector.currentData()'
    new_refresh = '''    def refresh(self) -> None:
        self._selection_timer.stop()
        self._pending_selection_index = -1
        current = self.selector.currentData()'''
    if block.count(old_refresh) != 1:
        raise ValueError('visualization.py: unexpected refresh structure')
    block = block.replace(old_refresh, new_refresh, 1)

    hook = '    def _selection_changed(self, index: int) -> None:'
    add_methods = '''    def _queue_selection_change(self, index: int) -> None:
        self._pending_selection_index = index
        self._selection_timer.start()

    def _apply_pending_selection(self) -> None:
        index = self._pending_selection_index
        self._pending_selection_index = -1
        if index >= 0:
            self._selection_changed(index)

'''
    if block.count(hook) != 1:
        raise ValueError('visualization.py: expected one selection method')
    block = block.replace(hook, add_methods + hook, 1)
    old_call = '''        if not path.is_file():
            return

        self.viewer.load_structure('''
    new_call = '''        if not path.is_file():
            return

        # Re-selecting an unchanged file should not rebuild its 3D scene.
        file_stat = path.stat()
        signature = (str(path.resolve()), file_stat.st_mtime_ns, file_stat.st_size)
        if signature == self._last_structure_signature:
            return
        self._last_structure_signature = signature

        self.viewer.load_structure('''
    if block.count(old_call) != 1:
        raise ValueError('visualization.py: unexpected load_structure call')
    block = block.replace(old_call, new_call, 1)
    return prefix + block + suffix


def patch_dist_html(text: str) -> str:
    if 'id="ssscreen-viewport-style"' in text:
        return text
    if '</head>' not in text or '<div id="app"></div>' not in text:
        raise ValueError('matterviz_dist/index.html has unexpected structure')
    style = ('    <style id="ssscreen-viewport-style">\n' +
             LAYOUT_RULES + '\n    </style>\n')
    return text.replace('</head>', style + '  </head>', 1)


def main():
    for rel in FILES:
        if not (ROOT / rel).is_file():
            raise SystemExit(f'ERROR: {rel} not found. Run in SS-Screen repository root.')
    # Never change the working WebGL2 JavaScript bundle.
    package = json.loads((ROOT / 'gui-matterviz/package.json').read_text(encoding='utf-8'))
    if 'patch-renderer.mjs' not in package.get('scripts', {}).get('postbuild', ''):
        raise SystemExit('ERROR: npm postbuild WebGL2 patch is not configured. Stop before npm build.')
    if not (ROOT / 'gui-matterviz/patch-renderer.mjs').is_file():
        raise SystemExit('ERROR: working patch-renderer.mjs not present.')

    original = {p: (ROOT / p).read_text(encoding='utf-8') for p in FILES}
    new = {
        APP: patch_app(original[APP]),
        CSS: patch_css(original[CSS]),
        GUI: patch_gui(original[GUI]),
        DIST_HTML: patch_dist_html(original[DIST_HTML]),
    }
    ast.parse(new[GUI], filename=str(GUI))
    changes = [p for p in FILES if new[p] != original[p]]
    if not changes:
        print('Already applied; no files changed.')
        return

    backups = ROOT / '.ssscreen_viewer_backup' / datetime.now().strftime('%Y%m%d-%H%M%S')
    # Vite has emptyOutDir: preserve the entire known-working WebGL2 bundle
    # before a future npm build. This allows recovery even if postbuild fails.
    shutil.copytree(ROOT / 'src/ssscreen/gui/matterviz_dist',
                    backups / 'matterviz_dist_snapshot')
    for rel in changes:
        destination = backups / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, destination)
    for rel in changes:
        (ROOT / rel).write_text(new[rel], encoding='utf-8')
    print(f'BACKUP_DIR={backups}')
    for rel in changes:
        print(f'UPDATED={rel}')
    print('IMPORTANT: Already-built HTML gets fullscreen CSS immediately.')
    print('For faster JSON switches, next run: cd gui-matterviz && npm run build')
    print('The postbuild script must preserve your working forceWebGL patch.')


if __name__ == '__main__':
    main()
