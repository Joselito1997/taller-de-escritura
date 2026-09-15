/* One-time setup action invoked through Obsidian's CLI. No plugin fork or background service. */
const fs = require('fs');
const path = require('path');
const {execFile} = require('child_process');

module.exports = async function start(app, obsidianVersion) {
  const vault = app.vault.adapter.basePath;
  const root = path.dirname(vault);
  const resultPath = path.join(root, 'installation-result.json');
  const installation = JSON.parse(fs.readFileSync(path.join(root, '.installer/installation.json'), 'utf8'));
  if (installation.vault !== vault) throw new Error('La bóveda abierta no es la preparada.');
  const prior = JSON.parse(fs.readFileSync(resultPath, 'utf8'));
  const resuming = prior.status === 'checking';
  if (!resuming && prior.status !== 'prepared') return prior; // Never replay an attempted request after interruption.
  const write = (data) => {
    const next = resultPath + '.tmp';
    fs.writeFileSync(next, JSON.stringify({...data, vault, observedAt: new Date().toISOString()}, null, 2) + '\n');
    fs.renameSync(next, resultPath);
  };
  const bin = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin');
  const python = path.join(bin, process.platform === 'win32' ? 'python.exe' : 'python');
  const env = {...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', PATH: [bin, path.dirname(installation.claude), process.env.PATH || ''].join(path.delimiter)};
  const run = (script, operation, manifest) => new Promise((resolve, reject) => {
    const args = [path.join(vault, '.claude/scripts', script), ...operation];
    if (manifest) args.push('--manifest', '-');
    const child = execFile(python, args, {env, timeout: 90000, maxBuffer: 4 * 1024 * 1024}, (error, stdout) => {
      try {
        const result = JSON.parse(stdout);
        if (error || result.ok !== true) reject(new Error(result.message || 'Falló una comprobación de instalación.'));
        else resolve(result);
      } catch (parseError) { reject(parseError); }
    });
    if (manifest) child.stdin.end(JSON.stringify(manifest));
  });
  try {
    write({status: 'starting', existingInstallation: resuming});
    const deadline = Date.now() + 60000;
    while ((!app.plugins.plugins.realclaudian || !app.plugins.plugins['obsidian-kanban']) && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    const claudian = app.plugins.plugins.realclaudian;
    const kanban = app.plugins.plugins['obsidian-kanban'];
    if (!claudian || !kanban) throw new Error('Los complementos no están cargados en Obsidian.');
    if (claudian.settings.locale !== 'es' || !['normal', 'yolo'].includes(claudian.settings.permissionMode)) {
      throw new Error('Claudian debe estar en español y en el modo de trabajo elegido por el autor, Seguro o YOLO.');
    }
    const compatibility = JSON.parse(fs.readFileSync(path.join(root, 'compatibility.json'), 'utf8'));
    const profile = compatibility.cooperative_profiles.find(p => p.enabled && (p.platform === (process.platform === 'win32' ? 'windows' : process.platform)));
    if (!profile) throw new Error('Falta el perfil comprobado de esta distribución.');
    const verified = await run('setup.py', ['verify'], {schema_version: 1, consent: true, cooperative_profile: profile.id});
    const readiness = await run('book.py', ['--vault', vault, 'readiness']);
    if (!readiness.ready) throw new Error('El ayudante aún no está preparado para trabajar.');
    const structure = await run('book.py', ['--vault', vault, 'check'], {action: 'layout'});
    if (!structure.complete) throw new Error('Faltan carpetas del taller: ' + structure.missing.join(', '));
    const visibleFolders = structure.directories.map(item => item.path);
    const foldersVisible = () => visibleFolders.every(name => Array.isArray(app.vault.getAbstractFileByPath(name)?.children));
    const folderDeadline = Date.now() + 10000;
    while (!foldersVisible() && Date.now() < folderDeadline) await new Promise(resolve => setTimeout(resolve, 100));
    if (!foldersVisible()) throw new Error('Obsidian todavía no muestra todas las carpetas previstas.');
    let boardView;
    if (!resuming) {
      const note = app.vault.getAbstractFileByPath('inicio.md');
      const board = app.vault.getAbstractFileByPath('trabajo-pendiente.md');
      if (!note || !board) throw new Error('Faltan el inicio o el tablero.');
      await app.workspace.getLeaf(false).openFile(note);
      await app.workspace.getLeaf('tab').openFile(board);
      await new Promise(resolve => setTimeout(resolve, 500));
      boardView = app.workspace.getLeavesOfType('kanban').find(leaf => leaf.view.file?.path === 'trabajo-pendiente.md');
      if (!boardView) throw new Error('El tablero no se abrió con Kanban.');
    }
    await claudian.activateView();
    const view = app.workspace.getLeavesOfType('claudian-view')[0]?.view;
    let tab;
    while (!(tab = view?.getActiveTab()) && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 200));
    if (resuming) {
      if (!tab) throw new Error('Claudian no restauró su panel.');
      write({status: 'complete', existingInstallation: true, visibleFolders, message: 'Se conservó el libro y la conversación existente.', conversationId: tab.state.currentConversationId, readiness, verifiedProfile: verified.profile.profile_id});
      view.focusActiveInput();
      return JSON.parse(fs.readFileSync(resultPath, 'utf8'));
    }
    if (!tab || tab.state.isStreaming || tab.state.messages.length || tab.dom.inputEl.value.trim()) {
      throw new Error('Claudian ya contiene una conversación o un borrador; se conserva sin enviar otra bienvenida.');
    }
    const prompt = 'El agente instalador ya preparó este taller. Comprueba la instalación y tus instrucciones de entrada sin modificar el libro ni usar investigación. Si puedes empezar, dame una bienvenida en dos o tres frases e invítame a compartir todos los archivos que tenga del libro, aunque estén desordenados. Di que conservarás los originales y confirmaré contigo la reconstrucción antes de avanzar. No enumeres detalles técnicos ni tareas adicionales salvo un bloqueo que impida empezar.';
    write({status: 'sending', automaticSetupPrompt: prompt, model: installation.model, plugins: [claudian.manifest, kanban.manifest], obsidianVersion, boardView: 'kanban', readiness, verifiedProfile: verified.profile.profile_id});
    await tab.controllers.inputController.sendMessage({content: prompt});
    if (tab.state.isStreaming) throw new Error('La respuesta continúa en curso; conserve esta conversación.');
    const acceptedUser = tab.state.messages.find(message => message.role === 'user' && message.content === prompt);
    if (!acceptedUser) throw new Error('No se pudo confirmar que Claudian aceptó la petición inicial.');
    const assistant = [...tab.state.messages].reverse().find(message => message.role === 'assistant');
    const response = typeof assistant?.content === 'string' ? assistant.content : '';
    if (!response || !/(archivo|material|manuscrito|capítulo)/iu.test(response)) throw new Error('No se recibió la invitación esperada; revise la conversación original.');
    write({status: 'complete', model: installation.model, plugins: [claudian.manifest, kanban.manifest], obsidianVersion, boardView: 'kanban', visibleFolders, permissionMode: claudian.settings.permissionMode, safeMode: claudian.settings.providerConfigs.claude.safeMode, conversationId: tab.state.currentConversationId, acceptedUserMessageId: acceptedUser.id, assistantMessageId: assistant.id, assistantText: response, readiness, verifiedProfile: verified.profile.profile_id});
    view.focusActiveInput();
    return JSON.parse(fs.readFileSync(resultPath, 'utf8'));
  } catch (error) {
    write({status: 'failed', message: String(error.message || error), previousStatus: JSON.parse(fs.readFileSync(resultPath, 'utf8')).status});
    throw error;
  }
};
