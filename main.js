const { app, BrowserWindow, dialog, screen } = require('electron');
const { execFile } = require('child_process');
const path = require('path');
const attachDownloads = require('./desktop-downloads');
const attachUnsavedProtection = require('./desktop-unsaved');

function createWindow () {
  // Work-area dimensions are already in logical pixels, including Windows display scaling.
  const area = screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea;
  const width = Math.min(1400, area.width), height = Math.min(900, area.height);
  const mainWindow = new BrowserWindow({
    width,
    height,
    x: area.x + Math.floor((area.width - width) / 2),
    y: area.y + Math.floor((area.height - height) / 2),
    minWidth: Math.min(1024, width),
    minHeight: Math.min(650, height),
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#050505',
      symbolColor: '#ffffff',
      height: 35
    },
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  });

  // Load the main index.html
  attachDownloads(mainWindow);
  attachUnsavedProtection(mainWindow);
  mainWindow.loadFile(path.join(__dirname, 'index.html'));
  
  // Optionally open dev tools
  // mainWindow.webContents.openDevTools();
}

app.whenReady().then(async () => {
  // Direct Electron/npm launches must perform the same backend check as the launcher.
  try {
    await new Promise((resolve, reject) => {
      execFile('powershell.exe', ['-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        path.join(__dirname, 'scripts', 'desktop.ps1'), '-Action', 'Backend'],
      { cwd: __dirname, windowsHide: true, timeout: 150000 }, (error, stdout, stderr) => {
        if (error) reject(new Error((stdout + '\n' + stderr).trim() || error.message));
        else resolve();
      });
    });
  } catch (error) {
    dialog.showErrorBox('SmartEdit could not start the video backend', error.message);
    app.quit();
    return;
  }
  createWindow();

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});
