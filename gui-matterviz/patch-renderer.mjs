/**
 * SS-Screen / MatterViz 0.7.0: reliable WSL WebGL2 fallback.
 * IMPORTANT: use callback replacements for captured names.
 * Returning '$1' as a string from a replacement callback does NOT expand captures.
 *
 * This script is called by package.json's postbuild hook after `npm run build`.
 * It preserves the Vite source bundle and writes a distinct `*-webgl2.js`.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const dist = resolve(repoRoot, 'src/ssscreen/gui/matterviz_dist')
const indexPath = resolve(dist, 'index.html')
const html = readFileSync(indexPath, 'utf8')
const scriptRef = /(src=["'])(\.\/assets\/index-[^"']+\.js)(["'])/
const current = html.match(scriptRef)
if (!current) throw new Error('Cannot find Vite JS entry in matterviz_dist/index.html')

const sourceRel = current[2].replace(/-webgl2\.js$/, '.js')
const patchedRel = sourceRel.replace(/\.js$/, '-webgl2.js')
const sourcePath = resolve(dist, sourceRel)
const patchedPath = resolve(dist, patchedRel)
const source = readFileSync(sourcePath, 'utf8')

function replaceOnce(text, re, fn, description) {
  const matches = [...text.matchAll(re)]
  if (matches.length !== 1) {
    throw new Error(description + ': expected exactly 1 match, got ' + matches.length +
      '. Verify MatterViz bundle version before patching.')
  }
  return text.replace(re, fn)
}

// Do not gate 3D rendering solely on navigator.gpu; WebGL2 can work without WebGPU.
// Memoize this context test so Svelte reevaluations don't spawn many GL contexts.
let result = replaceOnce(
  source,
  /=\(\)=>typeof navigator<`u`&&`gpu`in navigator/g,
  () => '=(()=>{let __ssWebGL2Available;return()=>__ssWebGL2Available??=(typeof document<`u`&&!!document.createElement(`canvas`).getContext(`webgl2`))})()',
  'WebGL2 view feature gate',
)

// WebGPURenderer supports a WebGL2 backend when forceWebGL is true.
// Crucial: interpolate captured identifiers in this FUNCTION callback.
result = replaceOnce(
  result,
  /let ([\w$]+)=new ([\w$]+)\(\{canvas:([\w$]+),alpha:!0,antialias:!0,powerPreference:`high-performance`\}\);/g,
  (_whole, rendererName, constructorName, canvasName) =>
    `let ${rendererName}=new ${constructorName}({canvas:${canvasName},alpha:!1,antialias:!0,powerPreference:\`high-performance\`,forceWebGL:!0});` +
    `window.__ssScreenMVRenderer=${rendererName};` +
    `console.info('SSSCREEN_RENDERER_CREATED forceWebGL=true alpha=false');`,
  'WebGL renderer constructor',
)

result = replaceOnce(
  result,
  /([\w$]+)\.init\(\)\.catch\(([\w$]+)=>\{console\.error\(`WebGPU renderer initialization failed`,\2\)\}\)/g,
  (_whole, rendererName, errName) =>
    `${rendererName}.init().then(()=>{` +
    `console.info('SSSCREEN_RENDERER_READY backend='+(${rendererName}.backend?.constructor?.name??'unknown'));` +
    `setTimeout(()=>console.info('SSSCREEN_RENDER_STATS '+JSON.stringify({` +
    `backend:${rendererName}.backend?.constructor?.name??null,` +
    `frames:${rendererName}.info?.render?.frame??null,` +
    `drawCalls:${rendererName}.info?.render?.calls??null,` +
    `triangles:${rendererName}.info?.render?.triangles??null,` +
    `canvasWidth:${rendererName}.domElement?.width??null,` +
    `canvasHeight:${rendererName}.domElement?.height??null` +
    `})),2000);` +
    `}).catch(${errName}=>console.error('SSSCREEN_RENDERER_INIT_FAILED',${errName}))`,
  'WebGL renderer initialization result',
)

// Regression guard for the specific broken previous patch.
if (result.includes('new $2(') || result.includes('let $1=new $2(')) {
  throw new Error('Unexpanded capture placeholders detected in patched JS')
}

writeFileSync(patchedPath, result, 'utf8')
const patchedHtml = html.replace(scriptRef, (_all, prefix, rel, suffix) =>
  prefix + patchedRel + suffix,
)
writeFileSync(indexPath, patchedHtml, 'utf8')
console.log('[SS-Screen] Patched MatterViz WebGL2 JS:', basename(patchedPath))
console.log('[SS-Screen] Constructor captures interpolated correctly; no $2 placeholder')
