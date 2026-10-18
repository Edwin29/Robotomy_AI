// LEGACY: superseded by robotomy/native_input.py. Not used by current CLI/MCP.
// Historical sky implementation retained to explain earlier receipts, not for new runs.
// No direct Win32 input, injected gameplay methods, or hidden game-model access.
import fs from 'node:fs/promises';
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
const runFile = promisify(execFile);

export async function createBridge(sky, root) {
  root = path.resolve(root);
  const live = path.join(root, '.robotomy', 'live');
  const dir = path.join(live, 'control');
  const manifest = JSON.parse(await fs.readFile(path.join(live, 'isolation.json'), 'utf8'));
  const expectedExe = path.join(root, '.robotomy', 'runtime', 'LobotomyCorp', 'LobotomyCorp.exe');
  if (path.resolve(manifest.runtime) !== path.dirname(expectedExe)) throw Error('Unexpected private runtime.');
  const app = 'process:' + expectedExe;
  const bridgeId = randomUUID();
  let state = null, view = null, count = 0;
  const read = async p => JSON.parse(await fs.readFile(p, 'utf8'));
  const exists = async p => { try {await fs.access(p); return true;} catch {return false;} };
  const atomic = async (p, value) => {
    await fs.mkdir(path.dirname(p), {recursive:true});
    const tmp = p + '.' + randomUUID() + '.tmp';
    await fs.writeFile(tmp, JSON.stringify(value,null,2));
    await fs.rename(tmp,p);
  };
  async function event(kind, data) {
    const id = randomUUID();
    await atomic(path.join(dir,'events',Date.now()*1000000 + '_' + id + '.json'),
      {id, kind, at:new Date().toISOString(), ...data});
  }
  async function exporter() {
    const snap = await read(path.join(live,'latest.json'));
    const age = Date.now() - Date.parse(snap.captured_at_utc);
    if (!(age >= -5000 && age < 10000) || snap.environment !== 'lobotomy_live'
      || snap.isolation.company_name !== 'Robotomy_AI' || snap.isolation.product_name !== 'Lobotomy_Observer'
      || path.resolve(snap.isolation.persistent_data_path) !== path.resolve(manifest.isolated_save_path))
      throw Error('Stale or wrong isolated exporter.');
    return snap;
  }
  async function capture() {
    state = null; view = null;
    const windows = (await sky.list_windows()).filter(w=>w.app.toLowerCase() === app.toLowerCase());
    if (windows.length !== 1) throw Error('Expected one exact private game window.');
    const window = await sky.get_window({id:windows[0].id,app:windows[0].app});
    state = await sky.get_window_state({window, include_screenshot:true, include_text:false});
    const screenshot = state.screenshots[0];
    const snap = await exporter();
    if (!screenshot?.id || !screenshot.width || !screenshot.height) throw Error('No screenshot geometry.');
    view = {id:randomUUID().replaceAll('-',''), bridge_id:bridgeId, screenshot_id:screenshot.id,
      window_id:state.window.id, process_id:snap.process_id, scene:snap.scene,
      width:screenshot.width, height:screenshot.height, captured_epoch:Date.now()/1000};
    await atomic(path.join(dir,'view.json'),view);
    await atomic(path.join(dir,'views',view.id+'.json'),{view,snapshot:snap});
    return view;
  }
  async function executeOne() {
    const request = path.join(dir,'request.json');
    if (!await exists(request)) return {status:'idle'};
    const command = await read(request);
    if (!/^[a-f0-9]{32}$/.test(command.id)) throw Error('Invalid command id.');
    const receiptFile = path.join(dir,'receipts',command.id+'.json');
    const claimFile = path.join(dir,'claims',command.id+'.json');
    if (await exists(receiptFile)) {await fs.unlink(request); return read(receiptFile);}
    await fs.mkdir(path.dirname(claimFile),{recursive:true});
    try {await fs.writeFile(claimFile,JSON.stringify({at:new Date().toISOString()}),{flag:'wx'});}
    catch (e) {
      if (e.code === 'EEXIST') {await fs.unlink(request);return {id:command.id,status:'unknown',reason:'Already claimed; no replay.'};}
      throw e;
    }
    let receipt = {id:command.id, status:'rejected', at:new Date().toISOString()};
    let attempted = false;
    try {
      if (await exists(path.join(dir,'PAUSED'))) throw Error('Operator paused input.');
      const barrierPath=path.join(dir,'not-before.json');
      if (await exists(barrierPath) && command.created_epoch < (await read(barrierPath)).epoch)
        throw Error('Operator control changed after this decision.');
      if (count >= 60) throw Error('Bridge action budget exhausted.');
      if (!state || !view || command.view_id !== view.id || command.bridge_id !== bridgeId
        || command.screenshot_id !== view.screenshot_id || command.window_id !== state.window.id
        || Date.now()/1000 > command.expires_epoch || Date.now()/1000-view.captured_epoch>30)
        throw Error('Stale decision or lost screenshot binding; capture again.');
      const snap = await exporter();
      if (snap.process_id !== command.process_id || snap.scene !== command.scene) throw Error('Process or scene changed.');
      if (!['click','right_click','key','scroll'].includes(command.kind)) throw Error('Unsupported action.');
      if (command.kind === 'key') {
        if (!['space','Escape','Return','1','2','3','w','a','s','d','f','g'].includes(command.key)) throw Error('Key rejected.');
      } else if (!Number.isFinite(command.x) || !Number.isFinite(command.y)
          || command.x<0 || command.x>=view.width || command.y<24 || command.y>=view.height)
        throw Error('Coordinate outside game client.');
      if (command.kind==='scroll' && (!Number.isInteger(command.scroll_y) || Math.abs(command.scroll_y)>600 || command.scroll_y===0))
        throw Error('Scroll rejected.');
      // Read-only original save/prefs integrity verification; no shell/UI terminal invocation.
      await runFile(path.join(root,'.venv','Scripts','python.exe'),
        [path.join(root,'scripts','launch_live.py'),'--verify-only'],{cwd:root,windowsHide:true,timeout:15000});
      if (await exists(path.join(dir,'PAUSED')) || Date.now()/1000 > command.expires_epoch)
        throw Error('Paused or expired during verification.');
      if (await exists(barrierPath) && command.created_epoch < (await read(barrierPath)).epoch)
        throw Error('Operator control changed during verification.');
      const observation = state;
      state = null; view = null; // Consume this view before the input, including failures.
      attempted = true; count++;
      if (command.kind === 'key') await sky.press_key({window:observation.window,key:command.key});
      else if (command.kind === 'scroll') await sky.scroll({window:observation.window,screenshotId:command.screenshot_id,
        x:command.x,y:command.y,scrollX:0,scrollY:command.scroll_y});
      else await sky.click({window:observation.window,screenshotId:command.screenshot_id,
        x:command.x,y:command.y,mouse_button:command.kind==='right_click'?'right':'left'});
      receipt = {...receipt,status:'input_sent',at:new Date().toISOString(),
        boundary:'Input delivered; inspect a fresh observation to establish game outcome.'};
    } catch(e) {receipt = {...receipt,status:attempted?'unknown':'rejected',reason:String(e.message)};}
    await atomic(receiptFile,receipt);
    await event('input_receipt',{decision_id:command.id,...receipt});
    await fs.unlink(request);
    if (attempted) {
      try {receipt.next_view = await capture();}
      catch(e) {receipt.refresh_error=String(e.message);}
    }
    return receipt;
  }
  return {capture, executeOne, bridgeId};
}
