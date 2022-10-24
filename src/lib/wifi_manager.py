_D=False
_C='never'
_B=True
_A='wifi'
import json,time,os,network
try:import uasyncio as asyncio
except ImportError:pass
import log
class WifiManager:
    _ap_start_policy=_C;config_file='/networks.json'
    @classmethod
    def start_managing(cls):log.info(_A,'Starting to manage...');loop=asyncio.get_event_loop();loop.create_task(cls.manage())
    @classmethod
    async def manage(cls):
        while _B:
            status=cls.wlan().status()
            if status!=network.STAT_GOT_IP or cls.wlan().ifconfig()[0]=='0.0.0.0':log.info(_A,'Network not connected: managing');cls.setup_network()
            await asyncio.sleep(10)
    @classmethod
    def ifconfig(cls):return cls.wlan().ifconfig()
    @classmethod
    def wlan(cls):return network.WLAN(network.STA_IF)
    @classmethod
    def accesspoint(cls):return network.WLAN(network.AP_IF)
    @classmethod
    def wants_accesspoint(cls):
        static_policies={_C:_D,'always':_B}
        if cls._ap_start_policy in static_policies:return static_policies[cls._ap_start_policy]
        return cls.wlan().status()!=network.STAT_GOT_IP
    @classmethod
    def setup_network(cls):
        C='password';B='bssid';A='ssid'
        try:
            with open(cls.config_file,'r')as f:
                config=json.loads(f.read());cls.preferred_networks=config['known_networks'];cls.ap_config=config['access_point']
                if config.get('schema',0)!=2:log.warning(_A,'Did not get expected schema [2] in JSON config.')
        except Exception as e:log.error(_A,'Failed to load config file, no known networks selected');cls.preferred_networks=[];return
        cls.wlan().active(_B);available_networks=[]
        for network in cls.wlan().scan():ssid=network[0].decode('utf-8');bssid=network[1];strength=network[3];available_networks.append(dict(ssid=ssid,bssid=bssid,strength=strength))
        available_networks.sort(key=lambda station:station['strength'],reverse=_B);candidates=[]
        for aPreference in cls.preferred_networks:
            for aNetwork in available_networks:
                if aPreference[A]==aNetwork[A]:connection_data={A:aNetwork[A],B:aNetwork[B],C:aPreference[C]};candidates.append(connection_data)
        for new_connection in candidates:
            log.info(_A,'Attempting to connect to network {0}...'.format(new_connection[A]))
            if cls.connect_to(ssid=new_connection[A],password=new_connection[C],bssid=new_connection[B]):log.info(_A,'Successfully connected {0}'.format(new_connection[A]));break
        cls._ap_start_policy=cls.ap_config.get('start_policy',_C);should_start_ap=cls.wants_accesspoint();cls.accesspoint().active(should_start_ap)
        if should_start_ap:log.info(_A,'Enabling your access point...');cls.accesspoint().config(**cls.ap_config['config'])
        cls.accesspoint().active(cls.wants_accesspoint());return cls.wlan().isconnected()
    @classmethod
    def connect_to(cls,*,ssid,password,**kwargs):
        cls.wlan().connect(ssid,password,**kwargs)
        for check in range(0,10):
            if cls.wlan().isconnected():return _B
            time.sleep_ms(500)
        return _D