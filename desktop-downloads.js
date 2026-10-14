/* Keep completed exports in the native download flow, without opening a blank window. */
const { app, dialog } = require('electron');
const path = require('path');

function isExport(url) {
    try {
        const parsed = new URL(url);
        return parsed.origin === 'http://127.0.0.1:8000' && /^\/api\/studio\/jobs\/[a-f0-9]{32}\/file\/(video|subtitles|metadata)$/.test(parsed.pathname);
    } catch { return false; }
}

module.exports = function attachDownloads(win) {
    win.webContents.setWindowOpenHandler(({ url }) => {
        if (isExport(url)) { const download = new URL(url); download.searchParams.set('download','1'); win.webContents.downloadURL(download.href, {headers:{'Cache-Control':'no-cache'}}); return { action: 'deny' }; }
        return { action: 'allow', overrideBrowserWindowOptions: { webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } } };
    });
    const handler = (event, item, contents) => {
        if (contents !== win.webContents) return;
        item.setSaveDialogOptions({ title: 'Save edited video or export', defaultPath: path.join(app.getPath('downloads'), item.getFilename()) });
        item.once('done', (_, state) => {
            if (state === 'interrupted' && !win.isDestroyed()) dialog.showMessageBox(win, { type: 'error', message: 'Download interrupted', detail: 'Keep the local backend running and try Download edited MP4 again.' });
        });
    };
    const session = win.webContents.session;
    session.on('will-download', handler);
    win.on('closed', () => session.removeListener('will-download', handler));
};
