#!/usr/bin/python3

"""

Программа для копирования копирования публичного ssh-ключа на удаленные хосты из файла инвентори Ansible

"""
import threading

import re
import os
import socket
import argparse
import subprocess
from getpass import getpass

import paramiko


not_verbose = True


def get_host_name_and_ip(host: str) -> tuple:
    """
        Преобразует ip адрес в имя хоста, и наоборот
        Возвращает имя хоста и ip
    """

    try:
        if re.fullmatch('(\d{1,3}\.){3}\d{1,3}', host):
            ip = host
            hostname = socket.gethostbyaddr(ip)[0]
        else:
            hostname = host
            ip = socket.gethostbyname(hostname)
    except socket.gaierror as err:
        return None
    return hostname, ip


def parser_ansible_inventory_hosts(file_path_inventory: str, localhost=False) -> dict:
    """
        Парсит имена хостов и(или) ip адреса целевых хостов файла инвентори
    """

    with open(file_path_inventory, 'r', encoding='utf-8') as inventory_file:
        file_lines = inventory_file.readlines()
    # Удаляем пробельные символы в начале и в конце строки и склеиваем в единую строку для поиска хостов по рег. выражениям
    file_lines = [line.strip() for line in file_lines]

    raw_data_hosts = set()
    # Парсинг хостов если их значение храниться в переменной ansible_host
    pattern_ansible_hosts = re.compile(r"ansible_host\s*[:=]\s*(\S+)", flags=re.MULTILINE)
    findall_result_hosts = pattern_ansible_hosts.findall('\n'.join(file_lines))

    # парсинг хостов для всех остальных случаев
    # Удаляю строки, где есть в начале строки  совпадение переменных (идут через =), совпадение групп ([]) и коментарии (#)
    pattern_remove_line = re.compile(r'^\S+\s*[:=].*|^\[.+\].*|^\s*#.*', flags=re.MULTILINE)
    data_without_gr_var_comm = pattern_remove_line.sub('', '\n'.join(file_lines))
    data_without_gr_var_comm = [line.split()[0] for line in data_without_gr_var_comm.split('\n') if line]

    raw_data_hosts.update(findall_result_hosts + data_without_gr_var_comm)
    hosts = {}
    for host in raw_data_hosts.copy():
        host = re.sub('[\'\"]', '', host)
        hostname_and_ip = get_host_name_and_ip(host)
        if hostname_and_ip is not None:
            hostname, ip = hostname_and_ip
            hosts[hostname] = ip
    if not localhost and 'localhost' in hosts:
        del hosts['localhost']
    return hosts


def is_inventory(path: str, *name_file_inventory) -> bool:
    """
        Возвращает true если файл является ansible файлом inventory
    """

    name_file_inventory = name_file_inventory or ('inventory', 'host', 'hosts')
    pattern_inventory_search = r'/?\b((?:{})(?:\.(?:yaml|yml|ini))?)\b$'. \
                               format('|'.join(name_file_inventory))

    return re.search(pattern_inventory_search, path) if True else False


def search_inventory(root_path: str) -> list:
    inventroy_files = []
    for root, _, files in os.walk(root_path):
        for name in files:
            if is_inventory(name):
                inventroy_files.append(os.path.join(root, name))
    return inventroy_files


def generate_id_rsa(overwrite=False):
    path_ssh_dir = os.getenv('HOME') + '/.ssh'
    if not os.path.exists(path_ssh_dir):
        os.mkdir(path_ssh_dir)
    if not os.path.exists(path_ssh_dir + '/id_rsa') or overwrite:
        subprocess.run('echo yes | ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ""')


def deploy_key(key, host, username, password):
    # Удаляем предыдущую запись хоста
    try:
        client = paramiko.SSHClient()

        subprocess.call('ssh-keygen -f "{}/.ssh/known_hosts" -R {}'.format(os.getenv('HOME'), host), shell=True, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, username=username, password=password)
        client.exec_command('mkdir -p ~/.ssh/')
        _, stdout, _ = client.exec_command('cat ~/.ssh/authorized_keys')
        authorized_keys = stdout.read().decode('utf-8')
        if key not in authorized_keys:
            client.exec_command('echo "{}" > ~/.ssh/authorized_keys'.format(key))
            client.exec_command('chmod 644 ~/.ssh/authorized_keys')
            client.exec_command('chmod 700 ~/.ssh/')
            not_verbose and print('Ключ скопирован на хост {}'.format(host))
        else:
            not_verbose and print('Ключ был скопирован на хост {}'.format(host))
    except paramiko.ssh_exception.AuthenticationException as err:
        print(host, "    ", err)
    finally:
        client.close()


def copy_id_rsa_on_host(host, username, password):
    generate_id_rsa()
    with open(os.path.expanduser('~/.ssh/id_rsa.pub')) as file:
        key = file.read()
    deploy_key(key, host, username, password)


def argv_parser():
    parser = argparse.ArgumentParser(
        prog='sinit',
        description="Копирует публичный ключ rsa на удаленные хосты"
    )

    parser.add_argument('-p', dest='inventory_path', type=str, default='.', help='Путь к директории с файлом инвентори')
    parser.add_argument('-l', dest='list', nargs='+', help='Список хостов')
    parser.add_argument('-i', dest='inventory_name', nargs='+', help='путь или имя к файлу и')
    parser.add_argument('-u', dest='user', default=os.getlogin(), help='Имя пользователя под которым осуществляется подключение по ssh')
    parser.add_argument('-V', dest='not_verbose', action='store_true', help='Не выводить сообщения')
    # parser.add_argument('-f', '--file', type=str, default='.', help='Файл с ip адресами или с доменными именами')
    args = parser.parse_args()

    return args


def main():
    global not_verbose

    args = argv_parser()

    if args.not_verbose == True:
        not_verbose = False

    not_verbose and print('Подключение по ssh')
    not_verbose and print('Пользователь: {user}'.format(user=args.user))
    password = getpass('Введите пароль: ')

    if args.list is not None:
        hosts = args.list
    else:
        inventory_files = list(args.inventory_name) if args.inventory_name else search_inventory(args.inventory_path)

        hosts = {}
        for inventory in inventory_files:
            hosts.update(parser_ansible_inventory_hosts(inventory))
    not_verbose and print('Хостов для копирования: {}'.format(len(hosts)))

    threads = []
    for host in hosts:
        thread = threading.Thread(target=copy_id_rsa_on_host, args=(host, args.user, password))
        thread.start()
        threads.append(thread)

    for t in threads:
        t.join()



if __name__ == '__main__':
    main()
