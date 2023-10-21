import sys
import urllib.parse
import json
import os
import urllib.parse, urllib.request, urllib.error
import re, uuid
from time import time
from datetime import datetime
import math
import hashlib
from xml.dom import minidom
import xbmcaddon
import xbmcgui
import xbmcvfs
import requests
import xbmc


key = None;
mac = ':'.join(re.findall('..', '%012x' % uuid.getnode()));
sn = None;
device_id = None;
device_id2 = None;
signature = None;
stlink = None;
cache_version = '3'
dialog = xbmcgui.Dialog()
addon       = xbmcaddon.Addon('plugin.video.bluethunder')
addonname   = addon.getAddonInfo('name')
addondir    = xbmcvfs.translatePath( addon.getAddonInfo('profile') ) 



def is_json(myjson):
  try:
    json_object = json.loads(myjson)
  except ValueError as e:
    return False
  return True

def setMac(nmac):
    global mac;
    
    if re.match("[0-9a-f]{2}([-:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", nmac.lower()):
        mac = nmac;

def getMac():
    global mac;
    return mac;

def setSerialNumber(serial):
    global sn, device_id, device_id2, signature;
    
    if serial == None:
        return;
    
    elif serial['custom'] == False:
        sn = hashlib.md5(mac).hexdigest().upper()[13:];
        device_id = hashlib.sha256(sn).hexdigest().upper();
        device_id2 = hashlib.sha256(mac).hexdigest().upper();
        signature = hashlib.sha256(sn + mac).hexdigest().upper();

    elif serial['custom'] == True:
        sn = serial['sn'];
        device_id = serial['device_id'];
        device_id2 = serial['device_id2'];
        signature = serial['signature'];
        
def handshake(url):
    global key;
    
    if key != None:
        return;
    
    info = retrieveData(url, values = {
        'type' : 'stb', 
        'action' : 'handshake',
        'JsHttpRequest' : '1-xml'})
        
    key = info['js']['token']
    
    getProfile(url);

def getProfile(url):
    global sn, device_id, device_id2, signature;
    
    values = {
        'type' : 'stb', 
        'action' : 'get_profile',
        'hd' : '1',
        'ver' : 'ImageDescription:%200.2.18-r11-pub-254;%20ImageDate:%20Wed%20Mar%2018%2018:09:40%20EET%202015;%20PORTAL%20version:%204.9.14;%20API%20Version:%20JS%20API%20version:%20331;%20STB%20API%20version:%20141;%20Player%20Engine%20version:%200x572',
        'num_banks' : '1',
        'stb_type' : 'MAG254',
        'image_version' : '218',
        'auth_second_step' : '0',
        'hw_version' : '2.6-IB-00',
        'not_valid_token' : '0',
        'JsHttpRequest' : '1-xml'}

    if sn != None:
        values['sn'] = sn;
        values['device_id'] = device_id;
        values['device_id2'] = device_id2;
        values['signature'] = signature;


    info = retrieveData(url, values);

def retrieveData(url, values ):
    global key, mac;
        
    load = '/portal.php'
    refer = '/c/'
    timezone = 'America%2FChicago';

    user_agent     = 'Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 4 rev: 1812 Mobile Safari/533.3';
    
    if key != None:
        headers     = { 
            'User-Agent' : user_agent, 
            'Cookie' : 'mac=' + mac + '; stb_lang=en; timezone=' + timezone,
            'Referer' : url + refer,
            'Accept' : '*/*',
            'Connection' : 'Keep-Alive',
            'X-User-Agent' : 'Model: MAG254; Link: Ethernet',
            'Authorization' : 'Bearer ' + key };
    
    else:
        headers     = { 
            'User-Agent' : user_agent, 
            'Cookie' : 'mac=' + mac+ '; stb_lang=en; timezone=' + timezone,
            'Referer' : url + refer,
            'Accept' : '*/*',
            'Connection' : 'Keep-Alive',
            'X-User-Agent' : 'Model: MAG254; Link: Ethernet' };

    
    data = urllib.parse.urlencode(values).encode('utf-8');

    req = urllib.request.Request(url + load, data, headers);
    resp = urllib.request.urlopen(req).read().decode("utf-8");
    
    if not is_json(resp):
        req = urllib.request.Request(url + load + '?' + data, headers=headers);
        resp = urllib.request.urlopen(req).read().decode("utf-8");

    if not is_json(resp):
        raise Exception(resp)

    info = json.loads(resp)

    return info;


def getGenres(portal_mac, url, serial, path):    
    global key, cache_version;
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-genres';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    if not os.path.exists(path): 
        os.makedirs(path);
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
        
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url);
    
    info = retrieveData(url, values = {
        'type' : 'itv', 
        'action' : 'get_genres',
        'JsHttpRequest' : '1-xml'})
        
    
    results = info['js']
    
    data = '{ "version" : "' + cache_version + '", "time" : "' + str(now) + '", "genres" : {  \n'

    for i in results:
        alias     = i["alias"]
        id         = i["id"]
        title     = i['title']
        
        data += '"'+ id +'" : {"alias":"'+ alias +'", "title":"'+ title +'"}, \n'

    
    data = data[:-3] + '\n}}'

    with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    
    return json.loads(data.encode('utf-8'));

def getAllChannels(portal_mac, url, serial, path):
    global key;
    
    added = False;
    
    now = time();
    
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + 'channels'
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    if not os.path.exists(path):
        os.makedirs(path)

    if os.path.exists(portalurl):

        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
    
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url)
    

    genres = getGenres(portal_mac, url, serial, path);
    genres = genres["genres"];

    channels = []
    
    info = retrieveData(url, values = {
        'type' : 'itv', 
        'action' : 'get_all_channels',
        'JsHttpRequest' : '1-xml'})

    for result in info['js']['data']:
        channels.append({
            "id": result['id'],
            "number": result["number"],
            "name": result["name"],
            "cmd": result['cmd'],
            "logo": result["logo"],
            "tmp": result["use_http_tmp_link"],
            "genre_id": result['tv_genre_id'],
            })

    data = {
        "version" : cache_version,
        "time" : now,
        'channels' : channels,
    }
    with open(portalurl, 'w') as f:
        json.dump(data, f, indent=4)
    
    return data

def getVoDgenres(portal_mac, url, serial, path):    
    global key, cache_version;
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-vodgenres';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    if not os.path.exists(path):
        os.makedirs(path);
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
        
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url);
    
    info = retrieveData(url, values = {
        'type' : 'vod', 
        'action' : 'get_categories',
        'JsHttpRequest' : '1-xml'})
        
    
    results = info['js']
    
    data = '{ "version" : "' + cache_version + '", "time" : "' + str(now) + '", "vodgenres" : {  \n'

    for i in results:
        alias     = i["alias"]
        id         = i["id"]
        title     = i['title']
        cat     = i['id']
        
        data += '"'+ id +'" : {"alias":"'+ alias +'", "title":"'+ title +'", "cat":"'+ cat +'"}, \n'

    
    data = data[:-3] + '\n}}'

    with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    
    return json.loads(data.encode('utf-8'));

def getVoD(portal_mac, url, serial, path):#
    global key;
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cat     = args['cat'][0];
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-vod'+cat;
    
    setMac(portal_mac);
    #setSerialNumber(serial);
    
    if not os.path.exists(path):
        os.makedirs(path)
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
    
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url);
    
    data = '{ "version" : "' + cache_version + '", "time" : "' + str(now) + '", "vod'+cat+'" : [  \n'
    
    page = 1;
    pages = 300;
    total_items = 1.0;
    max_page_items = 1.0;
    
    while True:
        info = retrieveData(url, values = {
            'type' : 'vod', 
            'action' : 'get_ordered_list',
            'category' : cat,
            'sortby' : 'added',
            'not_ended' : '0',
            'p' : page,
            'fav' : '0',
            'JsHttpRequest' : '1-xml'})
        
        total_items = float(info['js']['total_items']);
        max_page_items = float(info['js']['max_page_items']);
        pages = math.ceil(total_items/max_page_items);
        
        results = info['js']['data']


        for i in results:
            name     = i["name"]
            cmd     = i['cmd']
            logo     = i["screenshot_uri"]
            plot    = i["description"]
            plot    = plot.replace('"',"-")
            plot    = plot.replace("r","")
            plot    = plot.replace("\n", " ")
            plot    = plot.replace("  "," ")
            genre    = i['genres_str']
            #cast     = i['actors']
            year     = i["year"]
            #imdb     = i['rating_imdb']

            data += '{'
            data += '"name":"' + name + '", '
            data += '"cmd":"' + cmd + '", '
            data += '"logo":"' + logo + '", '           
            data += '"plot":"' + plot + '", '
            data += '"genre":"' + genre + '", '
            #data += '"cast":"' + cast + '", '
            #data += '"imdb":"' + imdb + '", '           
            data += '"year":"' + year + '"}, \n'
            

        page += 1;
        if page > pages or page == 300:
            break;

    data = data[:-3] + '\n]}'

    with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    
    return json.loads(data.encode('utf-8'), strict=False);

def getSergenres(portal_mac, url, serial, path):    
    global key, cache_version;
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-sergenres';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    if not os.path.exists(path):
        os.makedirs(path);
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
        
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url);
    
    info = retrieveData(url, values = {
        'type' : 'series', 
        'action' : 'get_categories',
        'JsHttpRequest' : '1-xml'})
        
    
    results = info['js']
    
    data = '{ "version" : "' + cache_version + '", "time" : "' + str(now) + '", "sergenres" : {  \n'

    for i in results:
        alias     = i["alias"]
        id         = i["id"]
        title     = i['title']
        cat     = i['id']
        
        data += '"'+ id +'" : {"alias":"'+ alias +'", "title":"'+ title +'", "cat":"'+ cat +'"}, \n'

    
    data = data[:-3] + '\n}}'

    with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    
    return json.loads(data.encode('utf-8'));


def getSeries(portal_mac, url, serial, path):
    global key;
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cat     = args['cat'][0];
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-ser'+cat;
    
    setMac(portal_mac);
    #setSerialNumber(serial);
    
    if not os.path.exists(path):
        os.makedirs(path)
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file: data = json.load(data_file);
    
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(data['time']);
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data;
    
    handshake(url)
    
    series = []
    for page in range(1, 300):
        info = retrieveData(url, values = {
            'type' : 'series', 
            'action' : 'get_ordered_list',
            'category' : cat,
            'sortby' : 'added',
            'not_ended' : '0',
            'p' : page,
            'fav' : '0',
            'JsHttpRequest' : '1-xml'})
        
        total_items = info['js']['total_items']
        
        for result in info['js']['data']:
            plot = result["description"]
            plot = plot.replace('"',"-").replace("r","").replace("\n", " ").replace("  "," ")
            series.append({
                "category": result['category_id'],
                "cat": result["id"],
                "name": result["name"],
                "cmd": result['cmd'],
                "logo": result["screenshot_uri"],
                "plot": plot,
                "genre": result['genres_str'],
                "year": result["year"]
            })
        if len(series) >= total_items:
            break

    data = {
        "version" : cache_version,
        "time" : now,
        'ser'+cat: series,
    }
    with open(portalurl, 'w') as f:
        json.dump(data, f, indent=4)
        
    
    return data


def get_seasons(portal_mac, url, serial, path):
    global key;
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cat = args['cat'][0]
    category = args['category'][0]
    
    now = time();
    
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url))
    portalurl = os.path.join(path, portalurl + '-seasons'+cat)


    
    setMac(portal_mac)
    #setSerialNumber(serial)
    
    if not os.path.exists(path):
        os.makedirs(path)
    
    if os.path.exists(portalurl):
        #check last time
        with open(portalurl, 'rb') as data_file:
            data = json.load(data_file)
    
        if 'version' not in data or data['version'] != cache_version:
            clearCache(url, path)
            
        else:
            time_init = float(data['time'])
            # update 12h
            if ((now - time_init) / 3600) < 12:
                return data
    
    handshake(url)
    
    seasons = []
    for page in range(1, 300):
        info = retrieveData(url, values = {
            'type' : 'series', 
            'action' : 'get_ordered_list',
            'category' : category,
            'movie_id' : cat,
            'sortby' : 'added',
            'season_id' : '0',
            'episod_id' : '0',
            'p' : page,
            'JsHttpRequest' : '1-xml'})
            
        total_items = info['js']['total_items']

        for result in info['js']['data']:
            plot = result["description"]
            plot = plot.replace('"',"-").replace("r","").replace("\n", " ").replace("  "," ")
            seasons.append({
                "name":  result['name'],
                "category": result['category_id'],
                "cat": result["id"],
                "cmd": result['cmd'],
                "logo": result["screenshot_uri"],
                "plot": plot,
                "genre": result['genres_str'],
                "year": result["year"],
                "series": result["series"],
                })
        if len(seasons) >= total_items:
            break

    data = {
        "version" : cache_version,
        "time" : now,
        'seasons'+cat: seasons,
        }
    with open(portalurl, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=False)
   
    return data

def get_episodes(portal_mac, url, serial, path):
    global key;
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cat = args['cat'][0]
    category = args['category'][0]
    
    now = time();
    
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url))
    portalurl = os.path.join(path, portalurl + '-episodes')

    setMac(portal_mac)
    #setSerialNumber(serial)
    
    if not os.path.exists(path):
        os.makedirs(path)

    handshake(url)
    
    episodes = []
    for page in range(1, 5):
        info = retrieveData(url, values = {
            'type' : 'series', 
            'action' : 'get_ordered_list',
            'category' : category,
            'movie_id' : cat,
            'sortby' : 'added',
            'season_id' : '0',
            'episod_id' : '0',
            'p' : page,
            'JsHttpRequest' : '1-xml'})
            
        total_items = info['js']['total_items']
        
        dicts = info['js']['data']
        
        epi = next((index for (index, d) in enumerate(dicts) if d["id"] == cat), None)
        
        for item in info['js']['data'][epi]['series']:
            for result in info['js']['data']:
                episodes.append({
                    "episode": str(item),
                    "name":  result['name'],
                    "category": result['category_id'],
                    "cat": result["id"],
                    "cmd": result['cmd'],
                    "logo": result["screenshot_uri"],
                    "genre": result['genres_str'],
                    "year": result["year"],
                    "series": result["series"],
                    })
        if len(episodes) >= total_items:
            break

    data = {
        "version" : cache_version,
        "time" : now,
        'episodes': episodes,
        }
    with open(portalurl, 'w') as f:
        json.dump(data, f, indent=4, sort_keys=False)
   
    return data



    




def retriveUrl(portal_mac, url, serial, channel, tmp):
    
    setMac(portal_mac);
    setSerialNumber(serial);
        
    if 'matrix' in channel:
        return retrieve_matrixUrl(url, channel);
        
    else:
        return retrive_defaultUrl(url, channel, tmp);
 
def retrive_defaultUrl(url, channel, tmp):

    if tmp == '0':
        s = channel.split(' ');
        url = s[0];
        if len(s)>1:
            url = s[1];
        return url;


    handshake(url);
    
    cmd = channel;
    

    info = retrieveData(url, values = {
        'type' : 'itv', 
        'action' : 'create_link', 
        'cmd' : channel,
        'forced_storage' : 'undefined',
        'disable_ad' : '0',
        'JsHttpRequest' : '1-xml'});
    cmd = info['js']['cmd'];
        
    s = cmd.split(' ');
            
    url = s[0];
    
    if len(s)>1:
        url = s[1];


    # RETRIEVE THE 1 EXTM3U
    request = urllib.request.Request(url)
    request.get_method = lambda : 'HEAD'
    response  = urllib.request.urlopen(request);
    data = response.read();
    
    
    data = data.splitlines();
    data = data[len(data) - 1];

    # RETRIEVE THE 2 EXTM3U
    url = response.geturl().split('?')[0];
    url_base = url[: -(len(url) - url.rfind('/'))]
    return url_base + '/' + data;

    
    return url;

def retrieve_matrixUrl(url, channel):

    channel = channel.split('/');
    channel = channel[len(channel) -1];
    
    url += '/server/api/matrix.php?channel=' + channel + '&mac=' + mac;
    
    # RETRIEVE THE 1 EXTM3U
    request = urllib.request.Request(url)
    response  = urllib.request.urlopen(request);
    data = response.read();

    _s1 = data.split(' ');    
    data = _s1[0];
    if len(_s1)>1:
        data = _s1[len(_s1) -1];
    
    return data;

def retriveVoD(portal_mac, url, serial, video):
    
    setMac(portal_mac);
    setSerialNumber(serial);
        
    s = video.split(' ');
    url = s[0];
    if len(s)>1:
        url = s[1];

    
    url = url.replace('TOMTOM:', 'http://');
    

    # RETRIEVE THE 1 EXTM3U
    request = urllib.request.Request(url)
    response  = urllib.request.urlopen(request);
    url = response.geturl();


    # RETRIEVE THE 1 EXTM3U
    request = urllib.request.Request(url)
    #request.get_method = lambda : 'HEAD'
    response  = urllib.request.urlopen(request);
    data = response.read();
    data = data.splitlines();
    data = data[len(data) - 1];
    
    # RETRIEVE THE 2 EXTM3U
    url = response.geturl().split('?')[0];
    url_base = url[: -(len(url) - url.rfind('/'))]
    return url_base + '/' + data;

def orderChannels(channels):
          n_data = {};
          for i in channels:    
              number         = i["number"];
              n_data[int(number)] = i;
          
          ordered = sorted(n_data);
          data = {};
          for i in ordered:    
              data[i] = n_data[i];
              
          return list(data.values());

def getEpistream(portal_mac, url, serial, path):
    
    global key;
    
#    dp = xbmcgui.DialogProgressBG();
#    dp.create('IPTV', 'Loading ...');
    
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cmd     = args['cmd'][0];
    episode     = args['episode'][0]
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-stv';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    handshake(url);
    
#    dp.update(20);
    
    info = retrieveData(url, values = {
        'type' : 'vod', 
        'action' : 'create_link',
        'cmd' : cmd,
        'series' : episode,
        'JsHttpRequest' : '1-xml'})
        
#    dp.update(40);
    
    results = info['js']['cmd']
    results = results.replace("ffmpeg ","" )
    

    #portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    #portalurl = path + '/' + portalurl + '-token';
            
    #####response = requests.head(results)
    ##data = response.headers['Location']
    #with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    ##with open(portalurl, 'rb') as f:    
    ##    url = f.read()

       
    title     = args['episode'][0];
    name     = args['name'][0];
    
    title = title;
    
#    li = xbmcgui.ListItem(title, iconImage=logo_url); <modified 9.0.19
    li = xbmcgui.ListItem(title);
    
    li.setInfo('video', {'Title': 'Episode:'+title+'  '+name});
    xbmc.Player().play(item=results, listitem=li);
    
    
def getStream(portal_mac, url, serial, path):
    
    global key;
    
#    dp = xbmcgui.DialogProgressBG();
#    dp.create('IPTV', 'Loading ...');
    
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cmd     = args['cmd'][0];
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-stv';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    handshake(url);
    
#    dp.update(20);
    
    info = retrieveData(url, values = {
        'type' : 'vod', 
        'action' : 'create_link',
        'cmd' : cmd,
        'JsHttpRequest' : '1-xml'})
        
#    dp.update(40);
    
    results = info['js']['cmd']
    results = results.replace("ffmpeg ","" )
    

    #portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    #portalurl = path + '/' + portalurl + '-token';
            
    #####response = requests.head(results)
    ##data = response.headers['Location']
    #with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    ##with open(portalurl, 'rb') as f:    
    ##    url = f.read()

       
    title     = args['title'][0];
    logo_url     = args['logo_url'][0];
    
    title = title;
    
#    li = xbmcgui.ListItem(title, iconImage=logo_url); <modified 9.0.19
    li = xbmcgui.ListItem(title);
    
    li.setInfo('video', {'Title': title});
    xbmc.Player().play(item=results, listitem=li);

def getTvStream(portal_mac, url, serial, path):
    
    global key;
    
#    dp = xbmcgui.DialogProgressBG();
#    dp.create('IPTV', 'Loading ...');
    
    args = urllib.parse.parse_qs(sys.argv[2][1:])
    cmd     = args['cmd'][0];
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-stv';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    handshake(url);
    
#    dp.update(20);
    
    info = retrieveData(url, values = {
        'type' : 'itv', 
        'action' : 'create_link',
        'cmd' : cmd,
        'JsHttpRequest' : '1-xml'})
        
#    dp.update(40);
    
    results = info['js']['cmd']
    results = results.replace("ffmpeg ","" )
    

    #portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    #portalurl = path + '/' + portalurl + '-token';
            
    #####response = requests.head(results)
    ##data = response.headers['Location']
    #with open(portalurl, 'wb') as f: f.write(data.encode('utf-8'));
    ##with open(portalurl, 'rb') as f:    
    ##    url = f.read()

       
    title     = args['title'][0];
    logo_url     = args['logo_url'][0];
    
    title = title;
    
#    li = xbmcgui.ListItem(title, iconImage=logo_url); <modified 9.0.19
    li = xbmcgui.ListItem(title);
    
    li.setInfo('video', {'Title': title});
    xbmc.Player().play(item=results, listitem=li);
    

def getEPG(portal_mac, url, serial, path):
    global key, cache_version;
    
    now = time();
    portalurl = "_".join(re.findall("[a-zA-Z0-9]+", url));
    portalurl = path + '/' + portalurl + '-epg';
    
    setMac(portal_mac);
    setSerialNumber(serial);
    
    if not os.path.exists(path): 
        os.makedirs(path);
    
    if os.path.exists(portalurl):
        #check last time
        xmldoc = minidom.parse(portalurl);
        
        itemlist = xmldoc.getElementsByTagName('tv');
        
        version = itemlist[0].attributes['cache-version'].value;
        
        if version != cache_version:
            clearCache(url, path);
            
        else:
            time_init = float(itemlist[0].attributes['cache-time'].value);
            # update 2h
            if ((now - time_init) / 3600) < 2:
                return xmldoc.toxml(encoding='utf-8');
    

    channels = getAllChannels(portal_mac, url, serial, path);
    channels = channels['channels'];
    
    handshake(url);
    
    info = retrieveData(url, values = {
        'type' : 'itv', 
        'action' : 'get_epg_info',
        'period' : '6',
        'JsHttpRequest' : '1-xml'})


    results = info['js']['data'];
    
    doc = minidom.Document();
    base = doc.createElement('tv');
    base.setAttribute("cache-version", cache_version);
    base.setAttribute("cache-time", str(now));
    base.setAttribute("generator-info-name", "IPTV Plugin");
    base.setAttribute("generator-info-url", "http://www.xmltv.org/");
    doc.appendChild(base)


    for c in results:
        
        if not str(c) in channels:
            continue;
    
        channel = channels[str(c)];
        name = channel['name'];
        
        c_entry = doc.createElement('channel');
        c_entry.setAttribute("id", str(c));
        base.appendChild(c_entry)
        
        
        dn_entry = doc.createElement('display-name');
        dn_entry_content = doc.createTextNode(name);
        dn_entry.appendChild(dn_entry_content);
        c_entry.appendChild(dn_entry);
    

    for k,v in list(results.items()):
    
        channel = None;
        
        if str(k) in channels:
            channel = channels[str(k)];
        
        for epg in v:
        
            start_time     = datetime.fromtimestamp(float(epg['start_timestamp']));
            stop_time    = datetime.fromtimestamp(float(epg['stop_timestamp']));
            
            pg_entry = doc.createElement('programme');
            pg_entry.setAttribute("start", start_time.strftime('%Y%m%d%H%M%S -0000'));
            pg_entry.setAttribute("stop", stop_time.strftime('%Y%m%d%H%M%S -0000'));
            pg_entry.setAttribute("channel", str(k));
            base.appendChild(pg_entry);
            
            t_entry = doc.createElement('title');
            t_entry.setAttribute("lang", "en");
            t_entry_content = doc.createTextNode(['name']);
            t_entry.appendChild(t_entry_content);
            pg_entry.appendChild(t_entry);
            
            d_entry = doc.createElement('desc');
            d_entry.setAttribute("lang", "en");
            d_entry_content = doc.createTextNode(epg['descr']);
            d_entry.appendChild(d_entry_content);
            pg_entry.appendChild(d_entry);
            
            dt_entry = doc.createElement('date');
            dt_entry_content = doc.createTextNode(epg['on_date']);
            dt_entry.appendChild(dt_entry_content);
            pg_entry.appendChild(dt_entry);
            
            c_entry = doc.createElement('category');
            c_entry_content = doc.createTextNode(epg['category']);
            c_entry.appendChild(c_entry_content);
            pg_entry.appendChild(c_entry);
            
        
            if channel != None and channel['logo'] != '':
                i_entry = doc.createElement('icon');
                i_entry.setAttribute("src", url + ':8080/misc/logos/320/' + channel['logo']);
                i_entry.appendChild(i_entry_content);
                pg_entry.appendChild(i_entry);

    
    with open(portalurl, 'wb') as f: f.write(doc.toxml(encoding='utf-8'));
    
    return doc.toxml(encoding='utf-8');

def main(argv):

      if argv[0] == 'load':
          #getAllChannels(argv[1], argv[2], None, argv[4]);
          data = getAllChannels(argv[1], argv[2], json.loads(argv[3]), argv[4]);
          
          
      elif argv[0] == 'genres':
          getGenres(argv[1], argv[2], None, argv[3]);

      elif argv[0] == 'vodgenres':
          getVoDgenres(argv[1], argv[2], None, argv[3]);

      elif argv[0] == 'vod':
          getVoD('', argv[1], argv[2]);
          
      elif argv[0] == 'channel':         
          url = retriveUrl(argv[1], argv[2], json.loads(argv[3]), argv[4], argv[5]);
          print (url)
    
      elif argv[0] == 'vod_url':
          url = retriveVoD('', argv[1], argv[2]);
          print (url)
          
      elif argv[0] == 'cache':
          clearCache(argv[1], argv[2]);
          
      elif argv[0] == 'profile':
          handshake(argv[1]);
 
      elif argv[0] == 'playvod':
          getVodPlay(argv[1]);
 
      elif argv[0] == 'epg':
          url = getEPG(argv[1], argv[2], json.loads(argv[3]), argv[4]);
          print (url)

      elif argv[0] == 'series':
          getsergenres('', argv[1], argv[2]);


if __name__ == "__main__":
   main(sys.argv[1:])