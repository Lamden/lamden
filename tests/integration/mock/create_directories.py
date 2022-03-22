import shutil
import pathlib


def create_fixture_directories(dir_list, root="./fixtures"):
    for d in dir_list:
        try:
            pathlib.Path(f'{root}/{d}').mkdir(parents=True, exist_ok=True)
        except FileExistsError:
            pass


def remove_fixture_directories(dir_list, root="./fixtures"):
    for d in dir_list:
        try:
            shutil.rmtree(f'{root}/{d}')
        except Exception as err:
            print(err)
            pass
