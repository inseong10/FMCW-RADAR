#!/usr/bin/env python3
"""Install the experiment recipe into a supplied PetaLinux project (no build)."""
import argparse
from datetime import datetime
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('project', type=Path)
    args = parser.parse_args()
    project = args.project.expanduser().resolve()
    config = project/'project-spec/configs/config'
    if not config.is_file():
        raise ValueError(f'Not a PetaLinux project: {project}')
    here = Path(__file__).resolve().parent
    recipe = project/'project-spec/meta-user/recipes-apps/fft128'
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    for name in ('fft128.bb', 'mmio.c', 'native_core.h', 'native_core.c', 'native_receiver.c'):
        dest = recipe/('files' if name != 'fft128.bb' else '')/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file():
            shutil.copy2(dest, dest.with_name(dest.name+'.bak_'+stamp))
        shutil.copy2(here/name, dest)
    # Add the menu entry. Actual selection stays in petalinux-config -c rootfs.
    menu = project/'project-spec/meta-user/conf/user-rootfsconfig'
    menu.parent.mkdir(parents=True, exist_ok=True)
    text = menu.read_text() if menu.exists() else ''
    if 'CONFIG_fft128' not in text.splitlines():
        if menu.exists():
            shutil.copy2(menu, menu.with_name(menu.name+'.bak_'+stamp))
        menu.write_text(text.rstrip()+'\nCONFIG_fft128\n')
    print(f'Installed {recipe}')
    print('Next: petalinux-config -c rootfs -> user packages -> fft128; enable it and save.')
    print('No boot image, kernel configuration or existing boot arguments were changed.')


if __name__ == '__main__':
    main()
