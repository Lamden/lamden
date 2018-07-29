import json

config = json.load(open('config.json'))

print(config['protocol'])