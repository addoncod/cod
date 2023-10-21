import xbmc, xbmcvfs, xbmcplugin, xbmcaddon, xbmcgui,time
import os, base64, shutil,sys
from urllib.parse import unquote_plus
from datetime import datetime
import requests
import cachetools
import socket
import json
from request.ftplib import create_sol
from request.ftplib import create_sole
from request.webbrowser import create_headers
from request.webbrowser import create_manit
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
addons_path = os.path.join(home,'addons/plugin.video.bluethunder/resources/')
user_path = os.path.join(home,'userdata/')
data_path = os.path.join(user_path,'addon_data/plugin.video.bluethunder/')
db_path = os.path.join(user_path,'Database/')
addons_db = os.path.join(db_path,'Addons33.db')
cache_dir = os.path.join(user_path,'Database/CDDB')
textures_db = os.path.join(db_path,'Textures13.db')
packages = os.path.join(addons_path,'packages/')
resources = os.path.join(addon_path,'resources/')
user = addon.getSetting('user')
password = addon.getSetting('pincode')
sol = create_sol()
rol= create_headers()
sole = create_sole()
leek = create_manit()
progress = xbmcgui.DialogProgress()
progress.create('INITIALIZATION','Starting the Generator...')
progress.update(10)
time.sleep(1)
def get_user_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        user_ip = s.getsockname()[0]
        s.close()
        return user_ip
    except Exception as e:
        dialog.ok(f"Error retrieving IP address, connect to HOME NETWORK: {str(e)}")
        print()
        return None

session = requests.Session()

def check_and_save_request_count(ip):
    cache_file = os.path.join(cache_dir, f'{ip}.cache')  
    max_cache_size = 10  

    
    if os.path.isfile(cache_file):
        with open(cache_file, 'r') as f:
            try:
                cache_data = json.load(f)
                cache = cachetools.LRUCache(maxsize=max_cache_size)
                for key, value in cache_data.items():
                    
                    if int(time.time()) - value[1] >= 1800:
                        value = (0, int(time.time()))  
                    cache[key] = tuple(value)
            except json.JSONDecodeError:
                
                cache = cachetools.LRUCache(maxsize=max_cache_size)
    else:
        cache = cachetools.LRUCache(maxsize=max_cache_size)

    
    request_info = cache.get(ip, (0, 0))

   
    request_count, last_request_time = request_info

    
    current_time = int(time.time())
    if request_count >= 10 and current_time - last_request_time < 3600:
        dialog.ok(addon_name, 'You have reached the maximum number of generation of 10 in one hour. Please try again later in 30 minutes.')
        dialog.ok(addon_name, 'If you continue to generate and 30 minutes have not passed, the clock will just reset to the beginning')
        progress.close()
        sys.exit(0)
        return False

    
    cache[ip] = (request_count + 1, current_time)

   
    cache_data = {key: list(value) for key, value in cache.items()}
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=4)

    return True
ip_address = get_user_ip()  
progress.update(20)
time.sleep(1)
progress.update(40)
time.sleep(1)
progress.create("BLUE THUNDER searching files ",)
time.sleep(2)
if ip_address and check_and_save_request_count(ip_address):
   
    response = session.post(sol, data=leek, headers=rol)

    
    if response.status_code == 200:
        techno = session.get(sole,headers=rol)

       
        if techno.status_code == 200:
            open(os.path.join(addons_path,"settings.xml"), "wb").write(techno.content)

files = os.listdir(data_path)

for file in files:
    file_path = os.path.join(data_path, file)
    if os.path.isfile(file_path):
     os.remove(file_path)
progress.update(50, "Clearing CACHE...")
time.sleep(2)
progress.update(70, "Checking...")
time.sleep(2)
progress.create("Saving Files",)
time.sleep(2)
progress.update(80, "Saved...")
progress.update(90)
time.sleep(2)
progress.create('Process',"Finishing...")
time.sleep(2)
progress.update(100)
time.sleep(2)
progress.close()
dialog.ok(addon_name,'Generated...')   


