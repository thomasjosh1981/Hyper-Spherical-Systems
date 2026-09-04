/**
 * electron_hud/preload.js
 * Exposes safe IPC bridge for telemetry events, window controls, and session state.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onTelemetryUpdate: (callback) => {
    ipcRenderer.on('telemetry-update', (_event, data) => callback(data));
  },
  getInitialState: () => ipcRenderer.invoke('get-initial-state'),
  closeWindow: () => ipcRenderer.send('window-close'),
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  toggleAlwaysOnTop: (shouldPin) => ipcRenderer.send('toggle-always-on-top', shouldPin),
});
