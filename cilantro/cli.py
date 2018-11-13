import click


@click.group()
def main():
    pass


@main.command('config', short_help='Adjust the default directory and network configuration.')
@click.option('-i', '--info', is_flag=True)
@click.option('-d', '--directory', 'directory')
@click.option('-n', '--network', 'network')
def config(info, directory, network):
    if info:
        print('printin')
    elif directory:
        print(directory)
    elif network:
        print(network)

if __name__ == '__main__':
    print('yo2')