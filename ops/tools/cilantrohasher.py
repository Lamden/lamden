# Python builtin imports
import os
import sys
import pathspec
import hashlib


class CilantroHasher(object):
    @staticmethod
    def _generate_gitignore_spec(path):
        with open(path, 'r') as f:
            lines = f.readlines()
            lines.append('.git/')
            lines.append('*.ipc')
            spec = pathspec.PathSpec.from_lines('gitwildmatch', lines)
        return spec

    @staticmethod
    def _filter_cilantro_files(cilantrodir, spec):
        allfiles = []
        for (dirpath, dirnames, filenames) in os.walk(cilantrodir):
            filenames = [ os.path.join(dirpath, filename) for filename in filenames ]
            allfiles.extend([ filename for filename in filenames if not spec.match_file(filename) ])
        return allfiles

    @staticmethod
    def _update_sha(filepath, sha):
        # Add filepath to sha to ensure empty files are tracked as well as the file contents
        sha.update(filepath.encode('utf-8'))
        with open(filepath, 'rb') as f:
            while True:
                block = f.read(2**10) # Magic number: one-megabyte blocks.
                if not block:
                    break
                sha.update(block)

    @classmethod
    def generate(cls):
        # Find cilantro directory, be sure to initiate filepath construction from the metadata of this file so we can call
        # this from anywhere
        cilantrodir = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
        spec = cls._generate_gitignore_spec(os.path.join(cilantrodir, '.gitignore'))
        files = cls._filter_cilantro_files(cilantrodir, spec)

        sha = hashlib.sha1()
        for fn in files:
            cls._update_sha(fn, sha)

        return sha.hexdigest()


if __name__ == "__main__":
    print(CilantroHasher.generate())
