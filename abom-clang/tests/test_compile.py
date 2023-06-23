from unittest import TestCase
from shlex import join as shlex_join
from tempfile import NamedTemporaryFile
from os.path import realpath, dirname, join
from contextlib import redirect_stdout
from io import StringIO
from random import choices
from string import ascii_lowercase, digits
from warnings import catch_warnings, simplefilter
from compile import compile
from check import check
from helpers import AbomMissingWarning

class TestAbom(TestCase):
    
    def resource(self, name):
        return join(dirname(realpath(__file__)), 'resources', name)

    def run_test(self, targets, checksums, compiler='clang', flags=[]):
        if not isinstance(targets, list) or not isinstance(checksums, list):
            raise TypeError('Targets and checksums must be lists.')
        with NamedTemporaryFile() as temp:
            # Test compiling
            compile_cmd = f'abom {compiler} {shlex_join(flags)} {shlex_join(map(self.resource, targets))} -o {temp.name}'
            try:
                with catch_warnings():
                    simplefilter('ignore', AbomMissingWarning)
                    compile(compile_cmd)
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
            check_cmd = f'abom-check {temp.name} {"".join(choices(ascii_lowercase + digits, k=64))}'
            with redirect_stdout(StringIO()) as stdout:
                try:
                    check(check_cmd)
                except SystemExit as e:
                    self.fail(f'Check failed: {e}')
            self.assertEqual('Absent', stdout.getvalue().strip())

    def test_hello_c(self):
        self.run_test(['hello.c'], ['d453920b4ebea035876a3e43af9f17e8d6ebb26f9ea084d2cdcee32d1c14a2ad'])

    def test_hello_bye_c(self):
        self.run_test(['hello.c', 'bye.c'], ['d453920b4ebea035876a3e43af9f17e8d6ebb26f9ea084d2cdcee32d1c14a2ad', '150cbf81b969bc2e17c12fb8e3ce9628fe22389c94bd6204e6c65fb943f7e9af'])

    def test_hello_cpp(self):
        self.run_test(['hello.cpp'], ['cf7741946e23dcbe01d80da6f2061d00976a8ee2002de5ed09ff279b0d386fcc'], compiler='clang++')