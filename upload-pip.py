import argparse, re, os, sys

file = 'setup.py'

with open(file) as f:
    file_content = f.read()
    p = re.compile(r'__version__ = \'([0-9]+)\.([0-9]+)+\.([0-9]+)\'')
    old_version = list(re.findall(p, file_content)[0])
    new_version = old_version[:]
    new_version[2] = str(int(new_version[2])+1)
    old_version = '.'.join(old_version)
    new_version = '.'.join(new_version)
    file_content = file_content.replace(old_version, new_version)

with open(file, 'w') as f:
    p = re.compile(r'name=[\'\"]([\w]+)[\'\"]')
    module_name = re.findall(p, file_content)[0]
    f.write(file_content)

os.system('python{} setup.py bdist_wheel'.format(sys.version_info.major))
os.system('twine upload dist/{}-{}-py3-none-any.whl'.format(module_name, new_version))
