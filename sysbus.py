import sys
import os
import pickle
import json
from collections import *
import tempfile
import schedule
import datetime
import time
from dateutil.tz import tz
from dateutil import parser as parsedate
import requests
import requests.utils
from influxdb import InfluxDBClient
from datetime import datetime


URL_LIVEBOX = ""
USER_LIVEBOX = ""
PASSWORD_LIVEBOX = ""
VERSION_LIVEBOX = ""

INFLUX_IP = ""
INFLUX_PORT = ""
INFLUX_DB = ""

session = None
sah_headers = None

def load_conf():
    global USER_LIVEBOX, PASSWORD_LIVEBOX, URL_LIVEBOX, VERSION_LIVEBOX, INFLUX_DB, INFLUX_IP, INFLUX_PORT
    
    try:
        URL_LIVEBOX = os.environ.get('URL_LIVEBOX')
        USER_LIVEBOX = os.environ.get('USER_LIVEBOX')
        PASSWORD_LIVEBOX = os.environ.get('PASSWORD_LIVEBOX')
        VERSION_LIVEBOX = os.environ.get('VERSION_LIVEBOX')
        INFLUX_IP = os.environ.get('INFLUX_IP')
        INFLUX_PORT = os.environ.get('INFLUX_PORT')
        INFLUX_DB = os.environ.get('INFLUX_DB')
    except:
        return False

    return True

def state_file():
    return tempfile.gettempdir() + "/" + "sysbus_state"

def auth(new_session=False):
    global session, sah_headers


    for i in range(2):

        if not new_session and os.path.exists(state_file()):
            with open(state_file(), 'rb') as f:
                cookies = requests.utils.cookiejar_from_dict(pickle.load(f))

                session = requests.Session()
                session.cookies = cookies

                contextID = pickle.load(f)

        else:
            session = requests.Session()

            auth = '{"service":"sah.Device.Information","method":"createContext","parameters":{"applicationName":"so_sdkut","username":"%s","password":"%s"}}' % (USER_LIVEBOX, PASSWORD_LIVEBOX)
            sah_headers = { 'Content-Type':'application/x-sah-ws-1-call+json', 'Authorization':'X-Sah-Login' }
            r = session.post(URL_LIVEBOX + 'ws', data=auth, headers=sah_headers)

            if not 'contextID' in r.json()['data']:
                error("auth error", str(r.text))
                break

            contextID = r.json()['data']['contextID']

            
            with open(state_file(), 'wb') as f:
                data = requests.utils.dict_from_cookiejar(session.cookies)
                pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
                data = contextID
                pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

        sah_headers = { 'X-Context':contextID,'X-Prototype-Version':'1.7','Content-Type':'application/x-sah-ws-1-call+json; charset=UTF-8','Accept':'text/javascript' }

        
        r = session.post(URL_LIVEBOX + 'sysbus/Time:getTime', headers=sah_headers, data='{"parameters":{}}')
        if r.json()['result']['status'] == True:
            print(r.json())
            return True
        else:
            os.remove(state_file())

    error("authentification impossible")
    return False

def requete(chemin, args=None, get=False, raw=False, silent=False):
   
    c = str.replace(chemin or "sysbus", ".", "/")
    if c[0] == "/":
        c = c[1:]

    if c[0:7] != "sysbus/":
        c = "sysbus/" + c

    if get:
        if args is None:
            c += "?_restDepth=-1"
        else:
            c += "?_restDepth="  + str(args)

        ts = datetime.datetime.now()
        t = session.get(URL_LIVEBOX + c, headers=sah_headers)
        t = t.content
    else:
        
        parameters = { }
        if not args is None:
            for i in args:
                parameters[i] = args[i]

        data = { }
        data['parameters'] = parameters
        sep = c.rfind(':')
        data['service'] = c[0:sep].replace('/', '.')
        if data['service'][0:7] == "sysbus.":
            data['service'] = data['service'][7:]
        data['method'] = c[sep+1:]
        c = 'ws'
        ts = datetime.now()
        t = session.post(URL_LIVEBOX + c, headers=sah_headers, data=json.dumps(data))
        t = t.content
    
    t = t.replace(b'\xf0\x44\x6e\x22', b'aaaa')

    if raw == True:
        return t

    t = t.decode('utf-8', errors='replace')
    if get and t.find("}{"):
        t = "[" + t.replace("}{", "},{") + "]"

    try:
        r = json.loads(t)
    except:
        if not silent:
            error("erreur:", sys.exc_info()[0])
            error("mauvais json:", t)
        return

    apercu = str(r)
    if len(apercu) > 50:
        apercu = apercu[:50] + "..."

    if not get and 'result' in r:
        if not 'errors' in r['result']:
            return r['result']
        else:
            if not silent:
                error("erreur:", t)
            return None

    else:
        return r
                                                                                                                                                                                      
def hosts_cmd():
    """ affiche la liste des hosts """
    r = requete("Hosts.Host:get")
    return r['status']

def main():
    global USER_LIVEBOX, PASSWORD_LIVEBOX, URL_LIVEBOX, VERSION_LIVEBOX, INFLUX_DB, INFLUX_IP, INFLUX_PORT

    load_conf()
    new_session = False

    if not auth(new_session):       
        sys.exit(1)
    ifx = InfluxDBClient(host=INFLUX_IP,port=INFLUX_PORT)
    ifx.create_database(INFLUX_DB)
    data=hosts_cmd()

    t=[]
    for k,v in data.items():
        d={}
        d["measurement"]="equipements"
        v['Active']=int(v['Active'])
        d["tags"]={"host": v['HostName']}
        d["fields"]=v
        t.append(d)

    ifx.write_points(t,database=INFLUX_DB)

if __name__ == '__main__':
    schedule.every(3).minutes.do(main)
    while True:
        schedule.run_pending()
        time.sleep
