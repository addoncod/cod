import sys
import os
import json
import urllib.request, urllib.parse, urllib.error
import urllib.parse
import xbmcaddon
import xbmcgui
import xbmcplugin
import load_channels
import hashlib
import re
import time
import xbmcvfs
import config
import shutil
from zipfile import ZipFile


addon       = xbmcaddon.Addon('plugin.video.bluethunder')
addonname   = addon.getAddonInfo('name')
addondir    = xbmcvfs.translatePath( addon.getAddonInfo('profile') ) 
dialog = xbmcgui.Dialog()
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
args = urllib.parse.parse_qs(sys.argv[2][1:])
go = True
icon0 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon.png')
icon2 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon2.png')
icon3 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon3.png')
icon4 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon4.png')
icon1 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon1.png')
icon6 = xbmcvfs.translatePath('special://home/addons/plugin.video.bluethunder/resources/icons/icon6.png')



xbmcplugin.setContent(addon_handle, 'movies')




def addPortal(portal):

    if portal['url'] == '':
        return;

    url = build_url({
        'mode': 'sel', 
        'portal' : json.dumps(portal)
        });   
    
    li = xbmcgui.ListItem(portal['name'])
    li.setArt({'icon':icon0})

    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True);
    #xbmcgui.Dialog().notification(addonname, '[COLOR lime]topeleven[/COLOR]',sound=False)
    
def build_url(query):
    return base_url + '?' + urllib.parse.urlencode(query)


def homeLevel():

    global portal_1, portal_2, portal_3, portal_4, portal_5, portal_6, portal_7, portal_8, portal_9, portal_10, portal_11, go;
    
    #todo - check none portal
    
 #boasvindas
    boas = xbmcgui.ListItem("[COLOR blue][B]Blue Thunder TV [/B][/COLOR]")
    boas.setArt({"icon": icon0})
    xbmcplugin.addDirectoryItem(handle=addon_handle, url="", listitem=boas, isFolder=False);   

    if go:
        addPortal(portal_1);
        addPortal(portal_2);
        addPortal(portal_3);
        addPortal(portal_4);
        addPortal(portal_5);
        addPortal(portal_6);
        addPortal(portal_7);
        addPortal(portal_8);
        addPortal(portal_9);
        addPortal(portal_10);
        addPortal(portal_11);
        
    
        xbmcplugin.endOfDirectory(addon_handle);

def SelectLevel():

    url = build_url({
        'mode': 'genres', 
        'portal' : json.dumps(portal)
        });
       
    
    li = xbmcgui.ListItem('[B]TELEVISION[/B]')
    li.setArt({'icon':icon1})

    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    
    url = build_url({
        'mode': 'vodgen', 
        'portal' : json.dumps(portal)
        });
       
    
    li = xbmcgui.ListItem('[B]VOD Movies[/B]')
    li.setArt({'icon':icon2})

    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)

    url = build_url({
        'mode': 'sergen', 
        'portal' : json.dumps(portal)
        });
       
    
    li = xbmcgui.ListItem('[B]VOD Tv Shows[/B]')
    li.setArt({'icon':icon3})

    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)    
    
    


    url = build_url({
        'mode': 'cache', 
        'portal' : json.dumps(portal)
        });
       
    
    li = xbmcgui.ListItem('Clear cache')
    li.setArt({'icon':icon4})

    xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    
    xbmcplugin.endOfDirectory(addon_handle);

    
    xbmcplugin.endOfDirectory(addon_handle);
    
    
 
def ClearLevel():
   filelist = [ f for f in os.listdir(addondir) if not f.endswith(".xml") ]
   for f in filelist:
       os.remove(os.path.join(addondir, f))
       
def genreLevel():
    
    try:
        data = load_channels.getGenres(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        
        return;

    data = data['genres'];
    
    for id, i in list(data.items()):

        title     = i["title"];
        
        url = build_url({
            'mode': 'channels', 
            'genre_id': id, 
            'genre_name': title.title(), 
            'portal' : json.dumps(portal)
            });
            
        if id == '10':
            iconImage = 'OverlayLocked.png';
        else:
            iconImage = 'DefaultVideo.png';
            
          
        li = xbmcgui.ListItem(title.title())
        li.setArt({'icon':icon1}) 
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True);
        

    xbmcplugin.endOfDirectory(addon_handle);

def channelLevel():
    stop=False;
        
    try:
        data = load_channels.getAllChannels(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        return;
    
    
    data = data['channels'];
    genre_name     = args.get('genre_name', None);
    
    genre_id_main = args.get('genre_id', None);
    genre_id_main = genre_id_main[0];
    
    if genre_id_main == '10' and portal['parental'] == 'true':
        result = xbmcgui.Dialog().input('Parental', hashlib.md5(portal['password'].encode('utf-8')).hexdigest(), type=xbmcgui.INPUT_PASSWORD, option=xbmcgui.PASSWORD_VERIFY);
        if result == '':
            stop = True;

    
    if stop == False:
        for i in data:
            
            name         = i["name"];
            cmd         = i["cmd"];
            tmp         = i["tmp"];
            number         = i["number"];
            genre_id     = i["genre_id"];
            logo         = i["logo"];
        
            if genre_id_main == '*' and genre_id == '10' and portal['parental'] == 'true':
                continue;
        
        
            if genre_id_main == genre_id or genre_id_main == '*':
        
                if logo != '':
                    logo_url = portal['url'] + '/stalker_portal/misc/logos/320/' + logo;
                else:
                    logo_url = 'DefaultVideo.png';
                
                
                url = build_url({
                    'mode': 'check', 
                    'cmd': cmd, 
                    'tmp' : tmp, 
                    'title' : name,
                    'genre_name' : genre_name,
                    'logo_url' : logo_url,  
                    'portal' : json.dumps(portal)
                    });
            

                li = xbmcgui.ListItem(name);
                li.setArt({'icon':logo})
                li.setInfo(type='Video', infoLabels={ 
                    'title': name,
                    'count' : number,
                    'plot' : "'No info'"
                    });

                xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li);
        
        xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_PLAYLIST_ORDER);
        xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_TITLE);
        xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_PROGRAM_COUNT);
        
        
        xbmcplugin.endOfDirectory(addon_handle);

def vodgenreLevel():
    
    try:
        data = load_channels.getVoDgenres(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        
        return;

    data = data['vodgenres'];
    
    for id, i in list(data.items()):

        title     = i["title"];
        cat     = i["cat"];
        
        url = build_url({
            'mode': 'vod', 
            'genre_name': title.title(),
            'cat' : cat,        
            'portal' : json.dumps(portal)
            });
            
        li = xbmcgui.ListItem(title.title())
        li.setArt({'icon':icon2})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True);
        

    xbmcplugin.endOfDirectory(addon_handle);

def vodLevel():
    
    try:
        data = load_channels.getVoD(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        return;
    cat     = args['cat'][0];    
    
    data = data['vod'+cat];
    
        
    for i in data:
        name     = i["name"];
        cmd     = i["cmd"];
        logo     = i["logo"];
        plot     = i["plot"];
        year     = i["year"];
        genre     = i["genre"];
        #cast     = i['cast'];
        #imdb     = i['imdb']
        
        #actors = [{"name": cast }]
        if logo != '':
            logo_url = portal['url'] + logo;
        else:
            logo_url = 'DefaultVideo.png';
                
                
        url = build_url({
                'mode': 'playvod', 
                'cmd': cmd, 
                'tmp' : '0', 
                'title' : name,
                'genre_name' : 'VoD',
                'logo_url' : logo_url, 
                'portal' : json.dumps(portal)
                });
            

        li = xbmcgui.ListItem(name )
        li.setInfo(type='Video', infoLabels={ 
                                            'title': name, 
                                            'plot' : plot, 
                                            'year' : year, 
                                            'genre' : genre,
                                            #'rating' : imdb
                                            #'cast' : list([cast])
                                            })
        #li.setCast(actors)
        #li.getRating('imdb', imdb )
        li.setArt({'icon':logo})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li)
    
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_UNSORTED);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_TITLE);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_GENRE);
    xbmcplugin.endOfDirectory(addon_handle);

def SeriesGenre():
    
    try:
        data = load_channels.getSergenres(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        
        return;

    data = data['sergenres'];
    
    for id, i in list(data.items()):

        title     = i["title"];
        cat     = i["cat"];
        
        url = build_url({
            'mode': 'seriescat', 
            'genre_name': title.title(),
            'cat' : cat,        
            'portal' : json.dumps(portal)
            });
            
        li = xbmcgui.ListItem(title.title())
        li.setArt({'icon':icon3})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True);
        

    xbmcplugin.endOfDirectory(addon_handle);


def SeriesLevel():
    
    try:
        data = load_channels.getSeries(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        
        return;
    cat     = args['cat'][0];    
    
    data = data['ser'+cat];
    
        
    for i in data:
        name     = i["name"];
        cmd     = i["cmd"];
        logo     = i["logo"];
        plot     = i["plot"];
        year     = i["year"];
        genre     = i["genre"];
        cat     = i['cat']
        category     = i['category']
        
        if logo != '':
            logo_url = portal['url'] + logo;
        else:
            logo_url = 'DefaultVideo.png';
                
                
        url = build_url({
                'mode': 'season', 
                'cat' : cat,                
                'name' : name,
                'cmd' : cmd,
                'category' : category,
                'logo_url' : logo_url, 
                'portal' : json.dumps(portal)
                });
            

        li = xbmcgui.ListItem(name )
        li.setInfo(type='Video', infoLabels={ 
                                            'name': name,                                            
                                            'plot' : plot, 
                                            'year' : year, 
                                            'genre' : genre,
                                            #'rating' : imdb
                                            #'cast' : list([cast])
                                            })
        #li.setCast(actors)
        #li.getRating('imdb', imdb )
        li.setArt({'icon':logo})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_UNSORTED);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_TITLE);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_GENRE);
    xbmcplugin.endOfDirectory(addon_handle);


def SeasonLevel():
    
    try:
        data = load_channels.get_seasons(portal['mac'], portal['url'], portal['serial'], addondir);
        
    except Exception as e:
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        return;
    cat     = args['cat'][0];    
    
    data = data['seasons'+ cat];
  
    for i in data:
        name     = i["name"];
        cmd     = i["cmd"];
        logo     = i["logo"];
        cat     = i["cat"];
        category     = i["category"];
        year     = i['year']
        plot     = i['plot']
        genre     = i['genre']

        
        if logo != '':
            logo_url = portal['url'] + logo;
        else:
            logo_url = 'DefaultVideo.png';
                
                
        url = build_url({
                'mode': 'episode',
                'cat' : cat,
                'category' : category,
                'name' : name,
                'cmd' : cmd,
                'portal' : json.dumps(portal)
                });
            

        li = xbmcgui.ListItem(name)
        li.setInfo(type='Video', infoLabels={ 
                                            'name': name,                                            
                                            'plot' : plot, 
                                            'genre' : genre,
                                            })
        
        li.setArt({'icon':logo})
        xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_UNSORTED);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_TITLE);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_GENRE);
    xbmcplugin.endOfDirectory(addon_handle);

def EpisodeLevel():
    cat     = args['cat'][0];    
    data = load_channels.get_episodes(portal['mac'], portal['url'], portal['serial'], addondir);

    data = data['episodes'];
  
    for i in data:
        name     = i["name"];
        cmd     = i["cmd"];
        cat     = i["cat"];
        category     = i["category"];
        series     = i["series"];
        episode     = i["episode"];

        url = build_url({
                'mode': 'epiplay',
                'episode' : episode,
                'name' : name,
                'cat' : cat,
                'category' : category,
                'cmd' : cmd,
                'portal' : json.dumps(portal)
                });
            
        cat1 = args.get('cat', None);
        cat1 = cat1[0];
        if cat1 == cat:
        
            li = xbmcgui.ListItem(str(episode))
            li.setInfo(type='Video', infoLabels={ 
                                            'name': episode,                                            
                                            })

            xbmcplugin.addDirectoryItem(handle=addon_handle, url=url, listitem=li, isFolder=True)
    
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_UNSORTED);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_TITLE);
    xbmcplugin.addSortMethod(addon_handle, xbmcplugin.SORT_METHOD_GENRE);
    xbmcplugin.endOfDirectory(addon_handle);

      
def checkcmd():
    cmd     = args['cmd'][0]
    if str(cmd).startswith('ffmpeg http://localhost') is True:
        load_channels.getTvStream(portal['mac'], portal['url'], portal['serial'], addondir);
    else:
        playLevel();



def playLevel():
    
    dp = xbmcgui.DialogProgressBG();
    dp.create('IPTV', 'Loading ...');
    
    title     = args['title'][0];
    cmd     = args['cmd'][0];
    tmp     = args['tmp'][0];
    genre_name     = args['genre_name'][0];
    logo_url     = args['logo_url'][0];
    
    try:
        if genre_name != 'VoD':
            url = load_channels.retriveUrl(portal['mac'], portal['url'], portal['serial'], cmd, tmp);
        else:
            url = load_channels.retrive_defaultUrl(portal['mac'], portal['url'], portal['serial'], cmd);

    
    except Exception as e:
        dp.close();
        xbmcgui.Dialog().notification(addonname, str(e), xbmcgui.NOTIFICATION_ERROR );
        return;

    
    dp.update(80);
    
    title = title;
    
    title += ' (' + portal['name'] + ')';
    
#    li = xbmcgui.ListItem(title, iconImage=logo_url); <modified 9.0.19
    li = xbmcgui.ListItem(title);
    li.setInfo('video', {'Title': title, 'Genre': genre_name});
    xbmc.Player().play(item=url, listitem=li);
    
    dp.update(100);
    
    dp.close();

def playStreamLevel():load_channels.getStream(portal['mac'], portal['url'], portal['serial'], addondir);
 
def PlayEpisode(): load_channels.getEpistream(portal['mac'], portal['url'], portal['serial'], addondir)
mode = args.get('mode', None);
portal =  args.get('portal', None)


if portal is None:
    portal_11 = config.portalConfig('11');
    portal_10 = config.portalConfig('10');
    portal_9 = config.portalConfig('9');
    portal_8 = config.portalConfig('8');
    portal_7 = config.portalConfig('7');
    portal_6 = config.portalConfig('6');
    portal_1 = config.portalConfig('1');
    portal_2 = config.portalConfig('2');
    portal_3 = config.portalConfig('3');
    portal_4 = config.portalConfig('4');
    portal_5 = config.portalConfig('5');
    
    
    

else:
    portal = json.loads(portal[0]);

#  Modification to force outside call to portal_1 (9.0.19)

    portal_2 = config.portalConfig('2');
    portal_3 = config.portalConfig('3');
    portal_4 = config.portalConfig('4');
    portal_5 = config.portalConfig('5');
    portal_6 = config.portalConfig('6');
    portal_7 = config.portalConfig('7');
    portal_8 = config.portalConfig('8');
    portal_9 = config.portalConfig('9');
    portal_10 = config.portalConfig('10');
    portal_11 = config.portalConfig('11');

    if not ( portal['name'] == portal_2['name'] or portal['name'] == portal_3['name'] or portal['name'] == portal_4['name'] or portal['name'] == portal_5['name'] or portal['name'] == portal_6['name'] or portal['name'] == portal_7['name'] or portal['name'] == portal_8['name'] or portal['name'] == portal_9['name'] or portal['name'] == portal_10['name'] or portal['name'] == portal_11['name'] ) :
        portal = config.portalConfig('1');

    

if mode is None:
    homeLevel();
    
elif mode[0] == 'cacheoptions':    
    CacheLevel();    
    
elif mode[0] == 'downcache':    
    getCache();
    
elif mode[0] == 'cache':    
    ClearLevel();

elif mode[0] == 'sel':
    SelectLevel();

elif mode[0] == 'genres':
    genreLevel();

elif mode[0] == 'vodgen':
    vodgenreLevel();
        
elif mode[0] == 'vod':
    vodLevel();

elif mode[0] == 'channels':
    channelLevel();
    
elif mode[0] == 'play':
    playLevel();

elif mode[0] == 'playvod':
    playStreamLevel();

elif mode[0] == 'check':
    checkcmd();

elif mode[0] == 'sergen':
    SeriesGenre();

elif mode[0] == 'seriescat':
    SeriesLevel();
    
elif mode[0] == 'season':
    SeasonLevel();

elif mode[0] == 'episode':
    EpisodeLevel();

elif mode[0] == 'epiplay':
    PlayEpisode();