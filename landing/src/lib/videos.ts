// El proyecto no incluye @types/node. Estos módulos solo corren al construir.
// @ts-expect-error node:fs no tiene tipos en este proyecto.
import * as fsNativo from 'node:fs';
// @ts-expect-error node:path no tiene tipos en este proyecto.
import * as pathNativo from 'node:path';
// @ts-expect-error node:url no tiene tipos en este proyecto.
import { fileURLToPath as rutaDeArchivo } from 'node:url';

const existsSync: (ruta: string) => boolean = fsNativo.existsSync;
const readFileSync: (ruta: string, codificacion: 'utf8') => string = fsNativo.readFileSync;
const resolve: (...partes: string[]) => string = pathNativo.resolve;
const join: (...partes: string[]) => string = pathNativo.join;
const dirname: (ruta: string) => string = pathNativo.dirname;
const fileURLToPath: (url: string) => string = rutaDeArchivo;

export type EstadoVideo = 'listo' | 'placeholder';

export interface VideoResuelto {
  nombre: string;
  titulo: string | null;
  descripcion: string | null;
  duracion: string | null;
  mp4: string | null;
  webm: string | null;
  poster: string | null;
  estado: EstadoVideo;
}

// En el build este módulo se empaqueta en otra carpeta: se busca la raíz que sí tenga public/videos.
const cwd = (globalThis as { process?: { cwd?: () => string } }).process?.cwd?.() ?? '.';
const raiz =
  [resolve(dirname(fileURLToPath(import.meta.url)), '../..'), cwd, join(cwd, 'landing')].find((r) =>
    existsSync(join(r, 'public', 'videos', 'videos.json')),
  ) ?? cwd;
const rutaManifiesto = join(raiz, 'public', 'videos', 'videos.json');

let manifiestoLeido = false;
let manifiestoCache: unknown | null = null;

function esPlano(valor: unknown): valor is Record<string, unknown> {
  return Boolean(valor) && typeof valor === 'object' && !Array.isArray(valor);
}

function texto(valor: unknown): string | null {
  if (typeof valor === 'string' && valor.trim()) return valor.trim();
  return null;
}

function textoEn(obj: Record<string, unknown>, claves: string[]): string | null {
  for (const clave of claves) {
    const hallado = texto(obj[clave]);
    if (hallado) return hallado;
  }
  return null;
}

function duracionDe(valor: unknown): string | null {
  const comoTexto = texto(valor);
  if (comoTexto) return comoTexto;
  if (typeof valor === 'number' && Number.isFinite(valor)) return String(valor);
  return null;
}

function normalizaNombre(valor: string): string {
  return valor.trim().toLowerCase();
}

/** Lee `public/videos/videos.json`. Si no existe o está mal formado, null. */
export function leerManifiesto(): unknown | null {
  if (manifiestoLeido) return manifiestoCache;
  manifiestoLeido = true;

  try {
    if (!existsSync(rutaManifiesto)) {
      manifiestoCache = null;
      return null;
    }
    const crudo = readFileSync(rutaManifiesto, 'utf8').replace(/^\uFEFF/, '');
    manifiestoCache = JSON.parse(crudo) as unknown;
    return manifiestoCache;
  } catch {
    manifiestoCache = null;
    return null;
  }
}

function entradas(manifiesto: unknown): Record<string, unknown>[] {
  if (Array.isArray(manifiesto)) return manifiesto.filter(esPlano);
  if (!esPlano(manifiesto)) return [];

  for (const clave of ['videos', 'clips', 'items', 'data', 'lista', 'manifiesto']) {
    const lista = manifiesto[clave];
    if (Array.isArray(lista)) return lista.filter(esPlano);
  }

  if (
    typeof manifiesto.nombre === 'string' ||
    typeof manifiesto.name === 'string' ||
    typeof manifiesto.id === 'string'
  ) {
    return [manifiesto];
  }

  const ignorar = new Set([
    'version',
    'meta',
    'generado',
    'generated',
    'updated',
    'fecha',
    '$schema',
    'schema',
  ]);
  const desdeMapa: Record<string, unknown>[] = [];

  for (const [clave, valor] of Object.entries(manifiesto)) {
    if (ignorar.has(clave) || !esPlano(valor)) continue;
    const explicito =
      texto(valor.nombre) ?? texto(valor.name) ?? texto(valor.id) ?? texto(valor.slug);
    desdeMapa.push({
      ...valor,
      nombre: explicito ?? clave,
      clave,
    });
  }

  return desdeMapa;
}

function coincide(entry: Record<string, unknown>, nombre: string): boolean {
  const buscado = normalizaNombre(nombre);
  const campos = [entry.nombre, entry.name, entry.id, entry.slug, entry.clave];
  return campos.some((campo) => typeof campo === 'string' && normalizaNombre(campo) === buscado);
}

function asignarSiFalta(plano: Record<string, unknown>, clave: string, ruta: string): void {
  const actual = plano[clave];
  if (typeof actual === 'string' && actual.trim()) return;
  plano[clave] = ruta;
}

function mediosDe(entry: Record<string, unknown>): Record<string, unknown> {
  const plano: Record<string, unknown> = { ...entry };

  for (const clave of ['archivos', 'files', 'sources', 'assets', 'formatos']) {
    const anidado = entry[clave];
    if (esPlano(anidado)) Object.assign(plano, anidado);
  }

  for (const clave of ['archivos', 'files', 'sources', 'assets', 'formatos']) {
    const lista = entry[clave];
    if (!Array.isArray(lista)) continue;
    for (const item of lista) {
      if (!esPlano(item)) continue;
      const tipo = (
        texto(item.tipo) ??
        texto(item.type) ??
        texto(item.formato) ??
        texto(item.format) ??
        ''
      ).toLowerCase();
      const ruta =
        texto(item.src) ??
        texto(item.ruta) ??
        texto(item.url) ??
        texto(item.path) ??
        texto(item.archivo);
      if (!ruta) continue;
      const lower = ruta.toLowerCase();
      if (tipo.includes('webm') || lower.includes('.webm')) asignarSiFalta(plano, 'webm', ruta);
      else if (tipo.includes('mp4') || lower.includes('.mp4')) asignarSiFalta(plano, 'mp4', ruta);
      else if (
        tipo.includes('poster') ||
        tipo.includes('image') ||
        tipo.includes('jpg') ||
        /\.(jpe?g|png|webp)(\?|#|$)/i.test(ruta)
      ) {
        asignarSiFalta(plano, 'poster', ruta);
      }
    }
  }

  return plano;
}

function aRutaPublica(valor: string): string | null {
  if (/^https?:\/\//i.test(valor)) return valor;
  const limpio = valor.replace(/\\/g, '/').trim();
  if (limpio.startsWith('//') || limpio.includes('..')) return null;
  let rel = limpio.replace(/^\.\//, '').replace(/^\//, '');
  if (rel.startsWith('public/')) rel = rel.slice('public/'.length);
  const sinQuery = rel.split('?')[0]?.split('#')[0] ?? rel;
  if (!sinQuery.includes('/')) rel = `videos/${rel}`;
  return `/${rel.replace(/^\//, '')}`;
}

function existePublica(ruta: string): boolean {
  if (/^https?:\/\//i.test(ruta)) return true;
  const sinQuery = ruta.split('?')[0]?.split('#')[0] ?? ruta;
  const rel = sinQuery.replace(/^\//, '');
  return existsSync(join(raiz, 'public', rel));
}

function primeraExistente(candidatos: Array<string | null>): string | null {
  const vistas = new Set<string>();
  for (const candidato of candidatos) {
    if (!candidato || vistas.has(candidato)) continue;
    vistas.add(candidato);
    const ruta = aRutaPublica(candidato);
    if (ruta && existePublica(ruta)) return ruta;
  }
  return null;
}

function porExtension(ruta: string | null, extension: string): string | null {
  if (!ruta) return null;
  const limpia = ruta.toLowerCase().split('?')[0]?.split('#')[0] ?? ruta.toLowerCase();
  return limpia.endsWith(extension) ? ruta : null;
}

/**
 * Resuelve un clip por `nombre`, `name` o `id`.
 * Si el JSON no lista archivos, prueba `/videos/<nombre>.mp4|webm` y el póster jpg.
 * Sin archivos en disco, `estado` es `placeholder`.
 */
export function obtenerVideo(nombre: string): VideoResuelto {
  const manifiesto = leerManifiesto();
  const entry = entradas(manifiesto).find((item) => coincide(item, nombre)) ?? null;
  const medios: Record<string, unknown> = entry ? mediosDe(entry) : {};
  const src = texto(medios.src);

  const mp4 = primeraExistente([
    textoEn(medios, ['mp4', 'h264', 'video_mp4', 'mp4Url', 'urlMp4']),
    porExtension(src, '.mp4'),
    `/videos/${nombre}.mp4`,
  ]);
  const webm = primeraExistente([
    textoEn(medios, ['webm', 'vp9', 'video_webm', 'webmUrl', 'urlWebm']),
    porExtension(src, '.webm'),
    `/videos/${nombre}.webm`,
  ]);
  const poster = primeraExistente([
    textoEn(medios, [
      'poster',
      'posterUrl',
      'poster_url',
      'portada',
      'imagen',
      'image',
      'thumbnail',
      'jpg',
    ]),
    porExtension(src, '.jpg'),
    porExtension(src, '.jpeg'),
    porExtension(src, '.png'),
    porExtension(src, '.webp'),
    `/videos/${nombre}-poster.jpg`,
    `/videos/${nombre}-poster.png`,
    `/videos/${nombre}-poster.webp`,
  ]);

  const listo = Boolean(mp4 || webm);

  return {
    nombre,
    titulo: entry
      ? (textoEn(entry, ['titulo', 'title', 'label']) ?? textoEn(medios, ['titulo', 'title']))
      : null,
    descripcion: entry
      ? (textoEn(entry, ['descripcion', 'description', 'desc', 'resumen', 'summary']) ??
        textoEn(medios, ['descripcion', 'description', 'desc']))
      : null,
    duracion: entry
      ? duracionDe(entry.duracion ?? entry.duration ?? entry.duracionSegundos ?? entry.durationSeconds)
      : null,
    mp4: listo ? mp4 : null,
    webm: listo ? webm : null,
    poster: listo ? poster : null,
    estado: listo ? 'listo' : 'placeholder',
  };
}
