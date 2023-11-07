from unittest import TestCase
from shlex import join as shlex_join
from tempfile import NamedTemporaryFile
from os.path import realpath, dirname, join
from contextlib import redirect_stdout
from io import StringIO
from random import randbytes
from warnings import catch_warnings, simplefilter
from build import build
from check import check
from helpers import AbomMissingWarning, hash_hex, INDEX_BYTES, TRAILING_NIBBLE

class TestAbom(TestCase):
    
    def resource(self, name):
        return join(dirname(realpath(__file__)), 'resources', name)

    def code_input_test(self, targets, checksums=None, compiler='clang', flags=[]):
        """ Run test for compiling ABOM from code input. Checksums are automatically calculated from targets if not provided. """
        if not isinstance(targets, list):
            raise TypeError('Targets must be lists.')
        
        if not checksums:
            checksums = []
            for target in targets:
                checksums.append(hash_hex(self.resource(target)))

        with NamedTemporaryFile() as temp:
            # Test compiling
            compile_cmd = f'abom {compiler} {shlex_join(flags)} {shlex_join(map(self.resource, targets))} -o {temp.name}'
            try:
                with catch_warnings():
                    simplefilter('ignore', AbomMissingWarning)
                    build(compile_cmd)
            except SystemExit as e:
                self.fail(f'Build failed: {e}')
            
            # Test abom-check (Present)
            for checksum in checksums:
                check_cmd = f'abom-check {temp.name} {checksum}'
                with redirect_stdout(StringIO()) as stdout:
                    try:
                        check(check_cmd)
                    except SystemExit as e:
                        self.fail(f'Check failed: {e}')
                self.assertEqual('Present', stdout.getvalue().strip())

            # Test abom-check (Absent)
            check_cmd = f'abom-check {temp.name} {randbytes(INDEX_BYTES).hex()[:-1 if TRAILING_NIBBLE else None]}'
            with redirect_stdout(StringIO()) as stdout:
                try:
                    check(check_cmd)
                except SystemExit as e:
                    self.fail(f'Check failed: {e}')
            self.assertEqual('Absent', stdout.getvalue().strip())

    def object_input_test(self, targets, checksums=None, compiler='clang', flags=[]):
        """ Run test for compiling ABOM from object input. Checksums are automatically calculated from targets if not provided."""
        if not isinstance(targets, list):
            raise TypeError('Targets must be lists.')
        
        if not checksums:
            checksums = []
            for target in targets:
                checksums.append(hash_hex(self.resource(target)))
        
        files = list(map(lambda x: (x,NamedTemporaryFile()), targets))

        # Test compiling
        for target,temp in files:
            compile_cmd = f'abom {compiler} -c {shlex_join(flags)} {self.resource(target)} -o {temp.name}'
            try:
                with catch_warnings():
                    simplefilter('ignore', AbomMissingWarning)
                    build(compile_cmd)
            except SystemExit as e:
                self.fail(f'Compilation failed: {e}')

        # Test linking
        with NamedTemporaryFile() as out:
            link_cmd = f'abom {compiler} {shlex_join(flags)} {shlex_join(map(lambda x: x[1].name, files))} -o {out.name}'
            try:
                with catch_warnings():
                    simplefilter('ignore', AbomMissingWarning)
                    build(link_cmd)
            except SystemExit as e:
                self.fail(f'Linking failed: {e}')
            
            # Test abom-check (Present)
            for checksum in checksums:
                check_cmd = f'abom-check {out.name} {checksum}'
                with redirect_stdout(StringIO()) as stdout:
                    try:
                        check(check_cmd)
                    except SystemExit as e:
                        self.fail(f'Check failed: {e}')
                self.assertEqual('Present', stdout.getvalue().strip())

            # Test abom-check (Absent)
            check_cmd = f'abom-check {out.name} {randbytes(INDEX_BYTES).hex()[:-1 if TRAILING_NIBBLE else None]}'
            with redirect_stdout(StringIO()) as stdout:
                try:
                    check(check_cmd)
                except SystemExit as e:
                    self.fail(f'Check failed: {e}')
            self.assertEqual('Absent', stdout.getvalue().strip())

        for _,temp in files:
            temp.close()

    def test_hello_c(self):
        self.code_input_test(['hello.c'])

    def test_hello_bye_c(self):
        self.code_input_test(['hello.c', 'bye.c'])

    def test_hello_cpp(self):
        self.code_input_test(['hello.cpp'], compiler='clang++')

    def test_hello_bye_c_obj(self):
        self.object_input_test(['hello.c', 'bye.c'])

    def test_hello_c_obj(self):
        self.object_input_test(['hello.c'])

    def test_hello_cpp_obj(self):
        self.object_input_test(['hello.cpp'], compiler='clang++')