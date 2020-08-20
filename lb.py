import requests
import requests.utils
import pickle
import tempfile
import datetime
import json
from influxdb import InfluxDBClient
import schedule
import time

session=None
sah_headers=None
USER_LIVEBOX="admin"
PASSWORD_LIVEBOX="Au7da5yz"
URL_LIVEBOX="http://192.168.1.1/"

def state_file():
    return tempfile.gettempdir() + "/" + "sysbus_state"

def requete(c, args=None, get=False, raw=False, silent=False):

    # complète les paramètres de la requête
    parameters = { }
    if not args is None:
        for i in args:
            parameters[i] = args[i]

    data = { }
    data['parameters'] = parameters

    # l'ihm des livebox 4 utilise une autre API, qui fonctionne aussi sur les lb2 et lb3
    sep = c.rfind(':')
    data['service'] = c[0:sep].replace('/', '.')
    if data['service'][0:7] == "sysbus.":
        data['service'] = data['service'][7:]
    data['method'] = c[sep+1:]
    c = 'ws'

    # envoie la requête avec les entêtes qui vont bien
    ts = datetime.datetime.now()
    t = session.post(URL_LIVEBOX + c, headers=sah_headers, data=json.dumps(data))

    return t.json()

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
            auth = { 'username':USER_LIVEBOX, 'password':PASSWORD_LIVEBOX }
            r = session.post('{0}authenticate'.format(URL_LIVEBOX), params=auth)
            if not 'contextID' in r.json()['data']:
                error("auth error", str(r.text))
                break

            contextID = r.json()['data']['contextID']

            # sauve le cookie et le contextID
            with open(state_file(), 'wb') as f:
                data = requests.utils.dict_from_cookiejar(session.cookies)
                pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)
                data = contextID
                pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)

        sah_headers = { 'X-Context':contextID,'X-Prototype-Version':'1.7','Content-Type':'application/x-sah-ws-1-call+json; charset=UTF-8','Accept':'text/javascript' }
        # vérification de l'authentification
        r = session.post(URL_LIVEBOX + 'sysbus/Time:getTime', headers=sah_headers, data='{"parameters":{}}')
        if r.json()['result']['status'] == True:
            return True
        else:
            os.remove(state_file())

    error("authentification impossible")
    return False

def main():
    auth(True)
    r = requete("Hosts/Host:get")
    client = InfluxDBClient('192.168.1.42', 8086, '', '', 'livebox_host')
    client.create_database('livebox_host')

    json_body = []
    measurements = ""

    for k,v in r['result']['status'].items():
        if v['Active'] :
            v['Active']=1
        else :
            v['Active']=0
        json_b={'measurement': 'host_activ', "tags": { 'hostname': v["HostName"]}, 'fields': v }
        json_body.append(json_b)
    
    client.write_points(json_body)

if __name__ == "__main__":
    schedule.every(30).seconds.do(main)

    while True:
        schedule.run_pending()
        time.sleep(1)
