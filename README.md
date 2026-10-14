Use the following command in the parent folder to package the game as a exe folder.
python -m PyInstaller --noconfirm --windowed --name rougeshot --hidden-import map_editor --add-data "Background\map_presets;Background\map_presets" --add-data "Assets;Assets" main.py
