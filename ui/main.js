// Ventana transparente, sin bordes, siempre encima.
//  - Al encender: anclada ABAJO-IZQUIERDA, tenue y click-through (no estorba el escritorio).
//  - Al llamarla ("Mike"/aplauso): despierta y se acomoda al CENTRO, interactiva.
//  - Para ejemplos largos: se expande a pantalla completa y vuelve sola.
// index.html habla con el núcleo Python por WebSocket (ws://127.0.0.1:8765).
const { app, BrowserWindow, screen, ipcMain } = require('electron');

const CHICO  = { w: 260, h: 260 };   // orbe anclado en la esquina
const CENTRO = { w: 460, h: 460 };   // orbe despierto al centro
let win;

function rectEsquina() {
  const wa = screen.getPrimaryDisplay().workAreaSize;
  return { x: 16, y: wa.height - CHICO.h - 16, width: CHICO.w, height: CHICO.h };
}
function rectCentro() {
  const wa = screen.getPrimaryDisplay().workAreaSize;
  return { x: Math.round((wa.width - CENTRO.w) / 2), y: Math.round((wa.height - CENTRO.h) / 2),
           width: CENTRO.w, height: CENTRO.h };
}

// Anima el tamaño/posición de la ventana con easing (en vez de saltar de golpe)
let anim = null;
function animarA(destino, ms = 300) {
  if (anim) clearInterval(anim);
  const ini = win.getBounds(), t0 = Date.now();
  const ease = k => 1 - Math.pow(1 - k, 3);   // easeOutCubic
  anim = setInterval(() => {
    const k = Math.min(1, (Date.now() - t0) / ms), e = ease(k);
    win.setBounds({
      x: Math.round(ini.x + (destino.x - ini.x) * e),
      y: Math.round(ini.y + (destino.y - ini.y) * e),
      width: Math.round(ini.width + (destino.width - ini.width) * e),
      height: Math.round(ini.height + (destino.height - ini.height) * e),
    });
    if (k >= 1) { clearInterval(anim); anim = null; }
  }, 16);
}

function anclar() {   // dormido: esquina, tenue, deja pasar los clics
  win.setIgnoreMouseEvents(true, { forward: true });
  animarA(rectEsquina());
}
function centrar() {  // despierto: al centro, interactivo
  win.setIgnoreMouseEvents(false);
  win.showInactive();  // se ve sin robar el foco de lo que estés haciendo
  animarA(rectCentro());
}

function crear() {
  win = new BrowserWindow({
    ...rectEsquina(),
    frame: false, transparent: true, alwaysOnTop: true, resizable: false,
    skipTaskbar: true, hasShadow: false, show: false,
    webPreferences: { nodeIntegration: true, contextIsolation: false },
  });
  win.setAlwaysOnTop(true, 'screen-saver');
  win.loadFile('index.html');
  // Arranca YA visible, anclado y tenue (no esperes a que lo llamen)
  win.once('ready-to-show', () => { anclar(); win.showInactive(); });
}

// La página pide: despertar al centro / volver a la esquina / expandir / contraer
ipcMain.on('ui', (_e, cmd) => {
  const { width, height } = screen.getPrimaryDisplay().size;
  if (cmd === 'centrar')  centrar();
  if (cmd === 'anclar')   anclar();
  if (cmd === 'expandir') { win.setIgnoreMouseEvents(false); animarA({ x: 0, y: 0, width, height }, 380); }
  if (cmd === 'contraer') anclar();
});

app.whenReady().then(crear);
app.on('window-all-closed', () => app.quit());
