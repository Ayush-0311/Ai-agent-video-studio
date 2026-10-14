/* Close uses the same Save / Discard / Keep editing decision as project switching. */
const {dialog} = require('electron');
module.exports = function attachUnsavedProtection(win) {
    let allowed = false, checking = false;
    win.on('close', event => {
        if (allowed) return;
        event.preventDefault();
        if (checking) return;
        checking = true;
        win.webContents.executeJavaScript('window.SmartEditSafety ? window.SmartEditSafety.requestClose() : true')
            .then(ok => { if (ok && !win.isDestroyed()) { allowed = true; win.close(); } })
            .catch(() => { if (!win.isDestroyed()) dialog.showErrorBox('Could not check unsaved work', 'Keep this window open and save your project before trying again.'); })
            .finally(() => { checking = false; });
    });
    win.webContents.on('will-prevent-unload', event => {
        const choice = dialog.showMessageBoxSync(win, {type:'question',buttons:['Keep editing','Discard and continue'],defaultId:0,cancelId:0,
            message:'This project has unsaved changes.',detail:'Keep editing to save your project before reloading or leaving this page.'});
        if (choice === 1) event.preventDefault();
    });
};
