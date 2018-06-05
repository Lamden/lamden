import os
import base64

def compose_msg(data=''):
    pepper = os.getenv('PEPPER','cilantro')
    if type(data) != list:
        data = [data]
    return bytearray(':'.join([pepper] + data), 'utf-8')

def decode_msg(msg):
    msg = msg.decode('utf-8')
    pepper = os.getenv('PEPPER','cilantro')
    if msg[:len(pepper)] == pepper:
        data = msg[len(pepper)+1:].split(':')
        return data[0], data[1:]
