import click


@click.group()
def main():
    pass


@main.command('config', short_help='Adjust the default directory and network configuration.')
def config():
    print('yo')

if __name__ == '__main__':
    print('yo2')