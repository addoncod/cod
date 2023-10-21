import xbmc, xbmcvfs, xbmcplugin, xbmcaddon, xbmcgui,time
import os, base64, shutil
from urllib.parse import unquote_plus
from datetime import datetime
addon_id = xbmcaddon.Addon().getAddonInfo('id')
EXCLUDES  = [addon_id,'packages','Addons33.db','kodi.log']
translatePath = xbmcvfs.translatePath
addon_id = xbmcaddon.Addon().getAddonInfo('id')
addon           = xbmcaddon.Addon(addon_id)
addoninfo       = addon.getAddonInfo
addon_version   = addoninfo('version')
addon_name      = addoninfo('name')
addon_icon      = addoninfo("icon")
addon_fanart    = addoninfo("fanart")
addon_profile   = translatePath(addoninfo('profile'))
addon_path      = translatePath(addoninfo('path'))
setting         = addon.getSetting
setting_true    = lambda x: bool(True if setting(str(x)) == "true" else False)
setting_set     = addon.setSetting
local_string    = addon.getLocalizedString
home = translatePath('special://home/')
dialog = xbmcgui.Dialog()
dp = xbmcgui.DialogProgress()
xbmcPath=os.path.abspath(home)
addons_path = os.path.join(home,'addons/plugin.video.HarleysListHarleysList/resources/')
user_path = os.path.join(home,'userdata/')
data_path = os.path.join(user_path,'addon_data/pvr.stalker/')
db_path = os.path.join(user_path,'Database/')
addons_db = os.path.join(db_path,'Addons33.db')
textures_db = os.path.join(db_path,'Textures13.db')
videos_db = os.path.join(db_path,'MyVideos121.db')
packages = os.path.join(addons_path,'packages/')
resources = os.path.join(addon_path,'resources/')
files = os.listdir(data_path)
progress = xbmcgui.DialogProgress()
progress.create('PVR STALKER CLIENT','Checking Stalker Client...')
xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.stalker", "enabled": false }}')
xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id":1, "method": "Addons.SetAddonEnabled", "params": { "addonid": "pvr.iptvsimple", "enabled": true }}')
progress.update(20, "PVR Stalker Client is disabled...")
time.sleep(3)
progress.update(40)
time.sleep(3)
progress.update(70, "Deleting PVR Data...")
def clear_pvr_data():
    xbmc.executebuiltin("PVR.ClearData")
    # Optionally, you can also reload the PVR client to ensure changes take effect
    xbmc.executebuiltin("PVR.ReloadGuide")

    # List all files in the folder
    files = os.listdir(data_path)

    # Iterate through the files and delete them
    for file in files:
        file_path = os.path.join(data_path, file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                print(f"Deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting {file_path}: {e}")

# Call the function to clear PVR data and delete files
clear_pvr_data()
xbmc.executebuiltin('InstallAddon(pvr.iptvsimple)')
time.sleep(10)
progress.close()
progress.create('Process',"IPTV SIMPLE CLIENT INSTALLED")
progress.update(80)
time.sleep(10)
progress.update(95,"CHECKING IPTV SIMPLE CLIENT...")
time.sleep(6)
progress.update(100,"YOU MUST SETUP IPTV SIMPLE CLIENT TO WORK")
time.sleep(10)
progress.close()
xbmc.executebuiltin('StartPVRManager')
dialog.ok(addon_name, 'IF YOU DONT KNOW HOW TO SETUP; CHECK WITH ADMINISTRATOR')
xbmc.executebuiltin("Addon.OpenSettings(pvr.iptvsimple)")
