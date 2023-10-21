import xbmc, xbmcaddon, xbmcgui, xbmcplugin, os, sys, xbmcvfs, glob
import shutil
import urllib.request, urllib.error, urllib.parse
import re
import zipfile
import fnmatch
import request as requests
import request
import hashlib
from datetime import date, datetime, timedelta
from urllib.parse import urljoin, parse_qsl
from resources.libs import extract, downloader,diss, notify, debridit, traktit, allucit, loginit, net, skinSwitch, uploadLog, yt, speedtest, wizard as wiz, addonwindow as pyxbmct
from request.webbrowser import create_headers
from request.webbrowser import create_man
from request.ftplib import create_mal
from request.ftplib import create_mano
from bs4 import BeautifulSoup

ADDON_ID         = diss.ADDON_ID
ADDONTITLE       = diss.ADDONTITLE
ADDON            = wiz.addonId(ADDON_ID)
VERSION          = wiz.addonInfo(ADDON_ID,'version')
ADDONPATH        = wiz.addonInfo(ADDON_ID, 'path')
DIALOG           = xbmcgui.Dialog()
DP               = xbmcgui.DialogProgress()
HOME             = xbmcvfs.translatePath('special://home/')
LOG              = xbmcvfs.translatePath('special://logpath/')
PROFILE          = xbmcvfs.translatePath('special://profile/')
TEMPDIR          = xbmcvfs.translatePath('special://temp')
ADDONS           = os.path.join(HOME,      'addons')
USERDATA         = os.path.join(HOME,      'userdata')
PLUGIN           = os.path.join(ADDONS,    ADDON_ID)
PACKAGES         = os.path.join(ADDONS,    'packages')
ADDOND           = os.path.join(USERDATA,  'addon_data')
ADDONDATA        = os.path.join(USERDATA,  'addon_data', ADDON_ID)
ADVANCED         = os.path.join(USERDATA,  'advancedsettings.xml')
SOURCES          = os.path.join(USERDATA,  'sources.xml')
FAVOURITES       = os.path.join(USERDATA,  'favourites.xml')
PROFILES         = os.path.join(USERDATA,  'profiles.xml')
GUISETTINGS      = os.path.join(USERDATA,  'guisettings.xml')
THUMBS           = os.path.join(USERDATA,  'Thumbnails')
DATABASE         = os.path.join(USERDATA,  'Database')
FANART           = os.path.join(PLUGIN,    'fanart.jpg')
ICON             = os.path.join(PLUGIN,    'icon.png')
ART              = os.path.join(PLUGIN,    'resources', 'art')
WIZLOG           = os.path.join(ADDONDATA, 'wizard.log')
SPEEDTESTFOLD    = os.path.join(ADDONDATA, 'SpeedTest')
ARCHIVE_CACHE    = os.path.join(TEMPDIR,   'archive_cache')
SKIN             = xbmc.getSkinDir()
BUILDNAME        = wiz.getS('buildname')
DEFAULTSKIN      = wiz.getS('defaultskin')
DEFAULTNAME      = wiz.getS('defaultskinname')
DEFAULTIGNORE    = wiz.getS('defaultskinignore')
BUILDVERSION     = wiz.getS('buildversion')
BUILDTHEME       = wiz.getS('buildtheme')
BUILDLATEST      = wiz.getS('latestversion')
SHOW15           = wiz.getS('show15')
SHOW16           = wiz.getS('show16')
SHOW17           = wiz.getS('show17')
SHOW18           = wiz.getS('show18')
SHOWADULT        = wiz.getS('adult')
SHOWMAINT        = wiz.getS('showmaint')
AUTOCLEANUP      = wiz.getS('autoclean')
AUTOCACHE        = wiz.getS('clearcache')
AUTOPACKAGES     = wiz.getS('clearpackages')
AUTOTHUMBS       = wiz.getS('clearthumbs')
AUTOFEQ          = wiz.getS('autocleanfeq')
AUTONEXTRUN      = wiz.getS('nextautocleanup')
INCLUDEVIDEO     = wiz.getS('includevideo')
INCLUDEALL       = wiz.getS('includeall')
INCLUDEBOB       = wiz.getS('includebob')
INCLUDEPHOENIX   = wiz.getS('includephoenix')
INCLUDESPECTO    = wiz.getS('includespecto')
INCLUDEGENESIS   = wiz.getS('includegenesis')
INCLUDEEXODUS    = wiz.getS('includeexodus')
INCLUDEONECHAN   = wiz.getS('includeonechan')
INCLUDESALTS     = wiz.getS('includesalts')
INCLUDESALTSHD   = wiz.getS('includesaltslite')
SEPERATE         = wiz.getS('seperate')
NOTIFY           = wiz.getS('notify')
NOTEID           = wiz.getS('noteid')
NOTEDISMISS      = wiz.getS('notedismiss')
TRAKTSAVE        = wiz.getS('traktlastsave')
REALSAVE         = wiz.getS('debridlastsave')
ALLUCSAVE        = wiz.getS('alluclastsave')
LOGINSAVE        = wiz.getS('loginlastsave')
KEEPFAVS         = wiz.getS('keepfavourites')
FAVSsave         = wiz.getS('favouriteslastsave')
KEEPSOURCES      = wiz.getS('keepsources')
KEEPPROFILES     = wiz.getS('keepprofiles')
KEEPADVANCED     = wiz.getS('keepadvanced')
KEEPREPOS        = wiz.getS('keeprepos')
KEEPSUPER        = wiz.getS('keepsuper')
KEEPWHITELIST    = wiz.getS('keepwhitelist')
KEEPTRAKT        = wiz.getS('keeptrakt')
KEEPREAL         = wiz.getS('keepdebrid')
KEEPALLUC        = wiz.getS('keepalluc')
KEEPLOGIN        = wiz.getS('keeplogin')
DEVELOPER        = wiz.getS('developer')
THIRDPARTY       = wiz.getS('enable3rd')
THIRD1NAME       = wiz.getS('wizard1name')
THIRD1URL        = wiz.getS('wizard1url')
THIRD2NAME       = wiz.getS('wizard2name')
THIRD2URL        = wiz.getS('wizard2url')
THIRD3NAME       = wiz.getS('wizard3name')
THIRD3URL        = wiz.getS('wizard3url')
BACKUPLOCATION   = ADDON.getSetting('path') if not ADDON.getSetting('path') == '' else 'special://home/'
BACKUPROMS       = wiz.getS('rompath')
MYBUILDS         = os.path.join(BACKUPLOCATION, 'My_Builds', '')
AUTOFEQ          = int(float(AUTOFEQ)) if AUTOFEQ.isdigit() else 0
TODAY            = date.today()
TOMORROW         = TODAY + timedelta(days=1)
THREEDAYS        = TODAY + timedelta(days=3)
KODIV          = float(xbmc.getInfoLabel("System.BuildVersion")[:4])
MCNAME           = wiz.mediaCenter()
EXCLUDES         = diss.EXCLUDES
CACHETEXT        = diss.CACHETEXT
CACHEAGE         = diss.CACHEAGE if str(diss.CACHEAGE).isdigit() else 30
BUILDFILE        = diss.BUILDFILE
ADDONPACK        = diss.ADDONPACK
APKFILE          = diss.APKFILE
YOUTUBETITLE     = diss.YOUTUBETITLE
YOUTUBEFILE      = diss.YOUTUBEFILE
ADDONFILE        = diss.ADDONFILE
ADVANCEDFILE     = diss.ADVANCEDFILE
UPDATECHECK      = diss.UPDATECHECK if str(diss.UPDATECHECK).isdigit() else 1
NEXTCHECK        = TODAY + timedelta(days=UPDATECHECK)
NOTIFICATION     = diss.NOTIFICATION
ENABLE           = diss.ENABLE
HEADERMESSAGE    = diss.HEADERMESSAGE
AUTOUPDATE       = diss.AUTOUPDATE  
BUILDERNAME      = diss.BUILDERNAME  
WIZARDFILE       = diss.WIZARDFILE
HIDECONTACT      = diss.HIDECONTACT
CONTACT          = diss.CONTACT
CONTACTICON      = diss.CONTACTICON if not diss.CONTACTICON == 'http://' else ICON 
CONTACTFANART    = diss.CONTACTFANART if not diss.CONTACTFANART == 'http://' else FANART
HIDESPACERS      = diss.HIDESPACERS
COLOR1           = diss.COLOR1
COLOR2           = diss.COLOR2
THEME1           = diss.THEME1
THEME2           = diss.THEME2
THEME3           = diss.THEME3
THEME4           = diss.THEME4
THEME5           = diss.THEME5
THEME6           = diss.THEME6
ICONBUILDS       = diss.ICONBUILDS if not diss.ICONBUILDS == 'http://' else ICON
ICONMAINT        = diss.ICONMAINT if not diss.ICONMAINT == 'http://' else ICON
ICONAPK          = diss.ICONAPK if not diss.ICONAPK == 'http://' else ICON
ICONADDONS       = diss.ICONADDONS if not diss.ICONADDONS == 'http://' else ICON
ICONYOUTUBE      = diss.ICONYOUTUBE if not diss.ICONYOUTUBE == 'http://' else ICON
ICONSAVE         = diss.ICONSAVE if not diss.ICONSAVE == 'http://' else ICON
ICONTRAKT        = diss.ICONTRAKT if not diss.ICONTRAKT == 'http://' else ICON
ICONREAL         = diss.ICONREAL if not diss.ICONREAL == 'http://' else ICON
ICONLOGIN        = diss.ICONLOGIN if not diss.ICONLOGIN == 'http://' else ICON
ICONCONTACT      = diss.ICONCONTACT if not diss.ICONCONTACT == 'http://' else ICON
ICONSETTINGS     = diss.ICONSETTINGS if not diss.ICONSETTINGS == 'http://' else ICON
Images           = xbmcvfs.translatePath(os.path.join('special://home','addons',ADDON_ID,'resources','images/'))
LOGFILES         = wiz.LOGFILES
TRAKTID          = traktit.TRAKTID
DEBRIDID         = debridit.DEBRIDID
LOGINID          = loginit.LOGINID
ALLUCID          = allucit.ALLUCID
MODURL           = 'http://tribeca.tvaddons.ag/tools/maintenance/modules/'
MODURL2          = 'http://mirrors.kodi.tv/addons/jarvis/'
INSTALLMETHODS   = ['Always Ask', 'Reload Profile', 'Force Close']
DEFAULTPLUGINS   = ['metadata.album.universal', 'metadata.artists.universal', 'metadata.common.fanart.tv', 'metadata.common.imdb.com', 'metadata.common.musicbrainz.org', 'metadata.themoviedb.org', 'metadata.tvdb.com', 'plugin.program.autocompletion']
#FTG MOD##
ROMPACK          = diss.ROMPACK
EMUAPKS          = diss.EMUAPKS
ROMPATH          = ADDON.getSetting('rompath') if not ADDON.getSetting('rompath') == '' else 'special://home/'
ROMLOC           = os.path.join(ROMPATH, 'Roms', '')
ers = create_headers()
user_path = os.path.join(HOME, 'userdata/')
data_path = os.path.join(user_path, 'addon_data/plugin.program.C.O.D')
progress = xbmcgui.DialogProgress()
dialog = xbmcgui.Dialog()
load = create_man()
###########################
#### Check Updates   ######
###########################

user_path = os.path.join(HOME, 'userdata/')
data_path = os.path.join(user_path, 'addon_data/plugin.program.C.O.D')
user = xbmcaddon.Addon('plugin.program.C.O.D').getSetting('user')
password = xbmcaddon.Addon('plugin.program.C.O.D').getSetting('pincode')
seek = create_mal()
reek = create_mano()
progress = xbmcgui.DialogProgress()
dialog = xbmcgui.Dialog()

###########################
#### Check Updates   ######
###########################

def SetPin():
    selected = dialog.select(('Choose an option'), [('Enter Username'), ('Delete Username')])
    if selected == -1:
        dialog.ok("C.O.D Wizard", 'Restart the application...')
        os._exit(1)
    elif selected == 0:
        user = AskPin1()
        if user:
            xbmcaddon.Addon('plugin.program.C.O.D').setSetting('user', user)
        pincode = AskPin()
        if pincode:
            xbmcaddon.Addon('plugin.program.C.O.D').setSetting('pincode', pincode)
    elif selected == 1:
        xbmcaddon.Addon('plugin.program.C.O.D').setSetting('user', '')
   
    return

        
def AskPin():
    pincode = dialog.input(('Enter the Password:'), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if pincode:
        return(pincode)
    return False

def AskPin1():
    user = dialog.input(('Enter Username:'))
    if user:
        xbmcaddon.Addon('plugin.program.C.O.D').setSetting('user', user)
    return False

def HashPinn(pin):
    pinhash = hashlib.sha256(pin.encode('ascii'))
    return pinhash.hexdigest()




def CheckPin():
    with requests.Session() as session:
        session = requests.get(seek, data=load, headers=ers)
        content = session.text
        m = requests.post(reek,data=load, headers=ers)
        soup = BeautifulSoup(m.content, "html.parser")
        p_tags = soup.find_all('strong')
        if len(p_tags ) > 0:
            for each in p_tags:
              mu = (str(each.get_text()))
              if (mu == user):
                 return True
              if (mu == "login"):
                 dialog.ok(user, 'You have not selected a package.You have to choose a package..')
                 dialog.ok(user, 'Unfortunately,  the application will close now...')
                 os._exit(1)
        else:
            retry = dialog.yesno(('You are not logged in...'), '{0}[CR]{1}?'.format(('Do you want to enter your Username or Password?'),('If you cannot log in, ask the administrator for help...')), yeslabel=('Yes'))
            if retry:
                return SetPin()
            else:
                dialog.ok(user, 'You are not logged in.Unfortunately,  the application will close now...')
                os._exit(1)
        
        
               
        
       
    return True
if CheckPin():
  from resources.libs import core