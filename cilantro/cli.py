import click
import os

configuration_path = '/usr/local/share/lamden'
configuration_filename = 'cilantro.conf'


def create_default_configuration_file():
    with open(configuration_path + '/' + configuration_filename, 'w') as f:
        f.write('./cilantro\n')
        f.write('127.0.0.1')


def get_configuration(filename):
    with open(filename) as f:
        directory = f.readline().rstrip('\n')
        network = f.readline()
    return directory, network


@click.group()
def main():
    pass


# make a directory in.. /usr/local/share/lamden
# cilantro.conf

@main.command('config', short_help='Adjust the default directory and network configuration.')
@click.option('-i', '--info', is_flag=True)
@click.option('-d', '--directory', 'directory')
@click.option('-n', '--network', 'network')
def config(info, directory, network):
    # make sure that the configuration_path path is available
    if not os.path.exists(configuration_path):
        os.makedirs(configuration_path)

    if not os.path.isfile(configuration_path + '/' + configuration_filename):
        create_default_configuration_file()

    if info:
        d, n = get_configuration(configuration_path + '/' + configuration_filename)
        print('Directory: {}'.format(d))
        print('Network Crawl: {}'.format(n))
    elif directory:
        print(directory)
    elif network:
        print(network)



# @main.command('new key', short_help='Testing spaces.')
# def new_key():
#     print('it do')


if __name__ == '__main__':
    print('yo2')