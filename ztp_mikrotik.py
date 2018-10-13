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

    # connect to router using ssh
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(hostname=ip, username=username, password=password, allow_agent=False, look_for_keys=False)

    config_list = [
        'ip address add address=192.168.1.1/24 interface=ether2',
        'ip pool add name=dhcp-server ranges=192.168.1.2-192.168.1.254',
        'ip dhcp-server add name=dhcp-server interface=ether2 address-pool=dhcp-server disabled=no',
        'ip dhcp-server network add address=192.168.1.0/24 gateway=192.168.1.1 dns-server=8.8.8.8',
        'ip firewall nat add chain=srcnat out-interface=pppoe-client action=masquerade',
        'ip service disable telnet,ftp,www,api,api-ssl',
        'ip firewall filter add action=drop chain=input comment="drop ssh brute forcers" dst-port=22 protocol=tcp src-address-list=ssh_blacklist',
        'ip firewall filter add action=add-src-to-address-list address-list=ssh_blacklist address-list-timeout=1w3d chain=input connection-state=new dst-port=22 protocol=tcp src-address-list=ssh_stage3',
        'ip firewall filter add action=add-src-to-address-list address-list=ssh_stage3 address-list-timeout=1m chain=input connection-state=new dst-port=22 protocol=tcp src-address-list=ssh_stage2',
        'ip firewall filter add action=add-src-to-address-list address-list=ssh_stage2 address-list-timeout=1m chain=input connection-state=new dst-port=22 protocol=tcp src-address-list=ssh_stage1',
        'ip firewall filter add action=add-src-to-address-list address-list=ssh_stage1 address-list-timeout=1m chain=input connection-state=new dst-port=22 protocol=tcp',
        'password old-password="" new-password="idnmantab" confirm-new-password="idnmantab"',
    ]

    for config in config_list:
        ssh_client.exec_command(config)
        time.sleep(0.2)

    # get info from router
    api = connect(username=username, password=password, host=ip)
    router_board_info = api(cmd="/system/routerboard/print")
    identity_info = api(cmd="/system/identity/print")

    identity = identity_info[0]['name']
    serial_number = router_board_info[0]['serial-number']
    model = router_board_info[0]['model']
    version = router_board_info[0]['upgrade-firmware']

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
