from flask import Flask, request, jsonify
import paramiko
import time
import telepot
from librouteros import connect
import MySQLdb as mdb

app = Flask(__name__)


@app.route('/configure', methods=['POST'])
def configure():
    dats = request.get_json()
    ip = dats['ip_router']
    username = 'admin'
    password = ''

    # get info from router
    api = connect(username=username, password=password, host=ip)
    router_board_info = api(cmd="/system/routerboard/print")
    identity_info = api(cmd="/system/identity/print")

    identity = identity_info[0]['name']
    serial_number = router_board_info[0]['serial-number']
    model = router_board_info[0]['model']
    version = router_board_info[0]['upgrade-firmware']

    # connect to router using ssh
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ip, username=username, password=password, allow_agent=False, look_for_keys=False)

    config_list = [
        'ip dns set servers=8.8.8.8',
        'ip address add address=192.168.1.1/24 interface=ether2',
        'ip pool add name=dhcp-server ranges=192.168.1.2-192.168.1.254',
        'ip dhcp-server add name=dhcp-server interface=ether2 address-pool=dhcp-server disabled=no',
        'ip dhcp-server network add address=192.168.1.0/24 gateway=192.168.1.1 dns-server=8.8.8.8',
        'ip service disable telnet,ftp,www,api-ssl',
        'ip firewall nat add chain=srcnat out-interface=pppoe-client action=masquerade',
        'ip firewall address-list add address=192.168.1.2-192.168.1.10 list=allowed_to_router',
        'ip firewall address-list add address=10.10.10.1 list=allowed_to_router',
        'ip firewall filter add action=accept chain=input src-address-list=allowed_to_router',
        'ip firewall filter add action=accept chain=input protocol=icmp',
        'ip firewall filter add action=drop chain=input',
        'ip firewall filter add action=drop chain=forward comment="Drop new connections from internet which are not dst-natted" connection-nat-state=!dstnat connection-state=new in-interface=pppoe-client',
        'password old-password="" new-password="idnmantab" confirm-new-password="idnmantab"',
        'user add name=noc password=noc123 disabled=no group=read',
        'tool bandwidth-server set enabled=no',
        'system clock set time-zone-name=Asia/Jakarta',
        'system ntp client set enabled=yes primary-ntp=202.162.32.12',
        'tool mac-server set allowed-interface-list=none',
        'tool mac-server mac-winbox set allowed-interface-list=none',
        'tool mac-server ping set enabled=no',
        'ip neighbor discovery-settings set discover-interface-list=none',
    ]

    # configure router
    for config in config_list:
        ssh_client.exec_command(config)
        time.sleep(0.2)

    # add info to the database
    sql_host = 'localhost'
    sql_username = 'root'
    sql_password = '***'
    sql_database = 'ztp_mikrotik'

    sql_conn = mdb.connect(sql_host, sql_username, sql_password, sql_database)
    cursor = sql_conn.cursor()

    cursor.execute("Use {}".format(sql_database))

    cursor.execute("INSERT INTO customer ({}, {}, {}, {}, {}) VALUES('{}', '{}', '{}', '{}', '{}')".format('identity', 'ip_address', 'serial_number', 'model', 'version', identity, ip, serial_number, model, version))

    sql_conn.commit()

    # send notification to telegram
    telegram_token = '<your_token>'
    chat_id = '<your_chat_id>'
    bot = telepot.Bot(telegram_token)
    bot.sendMessage(chat_id, 'Client Baru UP!\nIdentity: {}\nIP: {}\nSerial Number: {}\nModel: {}\nVersion: {}'.format(identity, ip, serial_number, model, version))

    data = {'status': 'ok'}

    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
