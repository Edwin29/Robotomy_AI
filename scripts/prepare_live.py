"""Create a private independent runtime; never modify the installed game or old saves."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / '.robotomy'
COMPANY, PRODUCT = 'Robotomy_AI', 'Lobotomy_Observer'


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
            raise RuntimeError(f'Reparse path requires manual review: {path}')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def assert_game_stopped() -> None:
    output = subprocess.check_output(['tasklist', '/FI', 'IMAGENAME eq LobotomyCorp.exe', '/FO', 'CSV'])
    if b'lobotomycorp.exe' in output.lower():
        raise RuntimeError('Close LobotomyCorp before preparing or launching the isolated copy.')


def prefs_snapshot() -> dict:
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Project_Moon\Lobotomy')
    except FileNotFoundError:
        return {}
    result = {}
    with key:
        for i in range(winreg.QueryInfoKey(key)[1]):
            name, value, kind = winreg.EnumValue(key, i)
            result[name] = [kind, value.hex() if isinstance(value, bytes) else value]
    return result


def prepare(source: Path) -> Path:
    import UnityPy
    assert_game_stopped()
    source = source.resolve(strict=True)
    runtime = PRIVATE / 'runtime' / 'LobotomyCorp'
    manifest_path = PRIVATE / 'live' / 'isolation.json'
    if runtime.exists() or manifest_path.exists():
        raise RuntimeError('An isolated runtime already exists; refusing to overwrite it.')
    old_saves = Path(os.environ['USERPROFILE']) / 'AppData/LocalLow/Project_Moon'
    new_saves = Path(os.environ['USERPROFILE']) / f'AppData/LocalLow/{COMPANY}/{PRODUCT}'
    if new_saves.parent.exists():
        raise RuntimeError(f'The target profile already exists: {new_saves.parent}')
    metadata = source / 'LobotomyCorp_Data/globalgamemanagers'
    env = UnityPy.load(str(metadata))
    objects = [obj for obj in env.objects if obj.type.name == 'PlayerSettings']
    if len(objects) != 1:
        raise RuntimeError('Expected exactly one PlayerSettings object.')
    before = objects[0].read_typetree()
    if (before['companyName'], before['productName']) != ('Project_Moon', 'Lobotomy'):
        raise RuntimeError('Unexpected installed game identity.')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = PRIVATE / 'backups' / stamp
    backup.mkdir(parents=True)
    original = inventory(old_saves)
    shutil.copytree(old_saves, backup / 'Project_Moon')
    if inventory(backup / 'Project_Moon') != original or inventory(old_saves) != original:
        raise RuntimeError('Save backup verification failed; no game will launch.')
    prefs = prefs_snapshot()
    (backup / 'original-playerprefs.json').write_text(json.dumps(prefs, ensure_ascii=False, indent=2), encoding='utf-8')
    cloud = []
    userdata = Path(os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')) / 'Steam/userdata'
    for file in userdata.glob('*/568220/remotecache.vdf'):
        target = backup / 'steam-cloud-metadata' / file.parent.parent.name / file.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
        cloud.append({'path': str(file), 'sha256': digest(file)})
    print(f'Backed up and verified {len(original)} original files at {backup}', flush=True)
    manifest = {'schema_version': 1, 'prepared_at_utc': stamp, 'source': str(source), 'runtime': str(runtime),
        'original_save_root': str(old_saves), 'isolated_save_path': str(new_saves), 'backup': str(backup),
        'original_save_hashes': original, 'original_preferences': prefs, 'cloud_metadata': cloud,
        'original_metadata_sha256': digest(metadata), 'prepared': False}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    def excluded(directory, names):
        # Installed user mods/backups are deliberately not activated in the copy.
        return [name for name in names if name in {'OST', 'BaseMods', 'BackUp'}]
    shutil.copytree(source, runtime, ignore=excluded)
    copied_metadata = runtime / 'LobotomyCorp_Data/globalgamemanagers'
    copied = UnityPy.load(str(copied_metadata))
    obj = next(obj for obj in copied.objects if obj.type.name == 'PlayerSettings')
    after = dict(before)
    after.update(companyName=COMPANY, productName=PRODUCT)
    obj.save_typetree(after)
    copied_metadata.write_bytes(copied.file.save())
    checked = UnityPy.load(str(copied_metadata))
    actual = next(obj for obj in checked.objects if obj.type.name == 'PlayerSettings').read_typetree()
    if actual != after:
        raise RuntimeError('Copied PlayerSettings verification failed.')
    # Documented Steam development launch convention prevents relaunching the original install.
    (runtime / 'steam_appid.txt').write_text('568220\n', encoding='ascii')
    return finish_build()


def finish_build() -> Path:
    import UnityPy
    assert_game_stopped()
    manifest_path = PRIVATE / 'live/isolation.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    runtime = Path(manifest['runtime']).resolve()
    if runtime != (PRIVATE / 'runtime/LobotomyCorp').resolve():
        raise RuntimeError('Unexpected runtime target.')
    copied_metadata = runtime / 'LobotomyCorp_Data/globalgamemanagers'
    env = UnityPy.load(str(copied_metadata))
    settings = next(obj for obj in env.objects if obj.type.name == 'PlayerSettings').read_typetree()
    if (settings['companyName'], settings['productName']) != (COMPANY, PRODUCT):
        raise RuntimeError('Runtime save isolation has not been applied.')
    mod_dir = runtime / 'LobotomyCorp_Data/BaseMods/RobotomyObserver'
    mod_dir.mkdir(parents=True, exist_ok=True)
    managed = runtime / 'LobotomyCorp_Data/Managed'
    references = ['mscorlib.dll', 'System.dll', 'System.Core.dll', 'UnityEngine.dll', 'UnityEngine.CoreModule.dll',
        'UnityEngine.UI.dll', 'UnityEngine.UIModule.dll', 'UnityEngine.IMGUIModule.dll',
        'UnityEngine.ImageConversionModule.dll', 'UnityEngine.JSONSerializeModule.dll', 'UnityEngine.ParticleSystemModule.dll',
        'UnityEngine.Physics2DModule.dll', 'UnityEngine.InputModule.dll', 'UnityEngine.AudioModule.dll', 'UnityEngine.AnimationModule.dll', 'UnityEngine.TextRenderingModule.dll', 'Assembly-CSharp.dll', '0Harmony.dll']
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    dll = mod_dir / 'RobotomyObserver.dll'
    subprocess.run([str(compiler), '/nologo', '/noconfig', '/target:library', '/nostdlib+', '/optimize+',
        f'/out:{dll}', *[f'/reference:{managed / name}' for name in references],
        str(ROOT / 'mods/RobotomyObserver/Observer.cs'),
        *[str(path) for path in sorted((ROOT / 'mods/RobotomyObserver').glob('*.cs')) if path.name != 'Observer.cs']], check=True)
    # Explicitly validated tutorial profile, never learned from whatever effect is currently active.
    # Do not replace a local operator profile. A different game build needs a fresh render audit.
    motion_profile = PRIVATE / 'live/motion-approved-profile.txt'
    if (not motion_profile.exists() and digest(managed / 'Assembly-CSharp.dll') ==
            'fb31a592f29a6d8a08e3884cf21d94bc8bd167c9aeefc2eef81a774c70b294bd'):
        shutil.copyfile(ROOT / 'config/motion-render-profile.txt', motion_profile)
    manifest.update(prepared=True, runtime_metadata_sha256=digest(copied_metadata), observer_sha256=digest(dll),
        runtime_exe_sha256=digest(runtime / 'LobotomyCorp.exe'))
    if (inventory(Path(manifest['original_save_root'])) != manifest['original_save_hashes']
            or prefs_snapshot() != manifest['original_preferences']
            or digest(Path(manifest['source']) / 'LobotomyCorp_Data/globalgamemanagers') != manifest['original_metadata_sha256']):
        raise RuntimeError('Original state changed while preparing; stop and inspect.')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (Path(manifest['backup']) / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Prepared isolated runtime. Manifest: {manifest_path}', flush=True)
    return manifest_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(r'D:\SteamLibrary\steamapps\common\LobotomyCorp'))
    parser.add_argument('--finish-build', action='store_true', help='Build/rebuild only the existing private observer with game closed.')
    args = parser.parse_args()
    finish_build() if args.finish_build else prepare(args.source)
